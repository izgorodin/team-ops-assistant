# Plan: Timezone Context Trigger & Resolution Pipeline

Создать context-aware pipeline для детекции ситуаций, когда нужно уточнить/резолвить timezone контекст. В отличие от простого детектора "есть ли TZ сигнал", этот подход анализирует контекст нескольких сообщений и детектит **необходимость резолва**.

## Ключевая идея

**Старый подход:** "В сообщении есть TZ сигнал" (regex/ML на "Мск", "PST")
**Новый подход:** "Нужно уточнить/резолвить TZ контекст" (ML на N последних сообщений)

### Что триггерит:
1. **Уточняющий вопрос** — "это по Москве?", "какая таймзона?"
2. **Явное указание TZ** — "по Мск", "PST", "UTC+3"
3. **Конфликт** — юзер в Тбилиси, но упоминает "московское время"
4. **Неоднозначность** — время без контекста в мультитаймзон чате

---

## Steps

### Phase 1: Dataset (ты делаешь)

1. **Создать датасет** [`data/tz_context_trigger_train.csv`](data/tz_context_trigger_train.csv)

   **Формат (простой — отдельные фразы):**
   ```csv
   phrase,has_tz_context,trigger_type,source_tz,notes
   "16:30 Мск",1,explicit_tz,Europe/Moscow,time + RU abbrev
   "это по москве?",1,clarification_question,,question about tz
   "встреча в 12",0,none,,no tz signal
   "в полдень по Тбилиси",1,explicit_tz,Asia/Tbilisi,по + city
   "какая у тебя таймзона?",1,clarification_question,,asking for tz
   "see you at 5pm PST",1,explicit_tz,America/Los_Angeles,EN abbrev
   "давай в 3",0,none,,just time no tz
   ```

   **Целевой размер:** ~200-300 строк

   **Категории trigger_type:**
   - `explicit_tz` — явное указание (Мск, PST, UTC+3, "по Тбилиси")
   - `clarification_question` — вопрос о таймзоне
   - `conflict` — TZ конфликт (для будущего, пока можно пропустить)
   - `none` — негативные примеры

2. **Расширить существующий** [`data/timezone_signals_train.csv`](data/timezone_signals_train.csv) — добавить RU паттерны, довести до ~300 строк (используем для regex extraction, не для trigger detection)

### Phase 2: ML Classifier (я делаю после датасета)

3. **Создать `TzContextTrigger`** в [`src/core/tz_context_trigger.py`](src/core/tz_context_trigger.py)
   - По образцу [`TimeClassifier`](src/core/time_classifier.py)
   - Input: текст сообщения (или concat последних N)
   - Output: `{triggered: bool, trigger_type: str, confidence: float}`

4. **Добавить LLM prompt** [`prompts/timezone_resolve.md`](prompts/timezone_resolve.md)
   ```markdown
   Context:
   - Recent messages: {messages}
   - Detected times: {times}
   - User TZ: {user_tz}
   - Chat users TZs: {chat_tzs}

   Question: What is the source timezone for the mentioned time(s)?

   Return JSON: {source_tz, confidence, reasoning}
   ```

5. **Расширить `llm_fallback.py`** — добавить `resolve_timezone_context()` с circuit breaker

### Phase 3: Integration

6. **Расширить `time_parse.py`** — добавить RU города в `CITY_TIMEZONES`, regex для "по {city}", "Мск", "Спб"

7. **Интегрировать в pipeline** — в [`TimeDetector`](src/core/triggers/time.py):
   ```python
   async def detect(self, event, recent_messages=None):
       times = parse_times(event.text)
       if not times:
           return []

       # Check if we need TZ resolution
       tz_trigger = tz_context_trigger.detect(event.text)
       if tz_trigger.triggered:
           source_tz = await resolve_tz(
               text=event.text,
               trigger_type=tz_trigger.trigger_type,
               user_tz=user_state.tz,
               recent_messages=recent_messages
           )
           # Attach source_tz to detected times
   ```

8. **Добавить `include_team_timezones: bool`** в [`ChatState`](src/core/models.py) — для chat-specific режимов

### Phase 4: Tests

9. **Написать тесты** — `tests/test_tz_context_trigger.py` + расширить `test_time_parser.py`

---

## Dataset Format Discussion

### Option A: Отдельные фразы (проще)
```csv
phrase,has_tz_context,trigger_type,source_tz,notes
"16:30 Мск",1,explicit_tz,Europe/Moscow,
"это по москве?",1,clarification_question,,
```
**Плюсы:** Простой формат, легко собирать, совместим с существующим TimeClassifier
**Минусы:** Теряем контекст нескольких сообщений

### Option B: JSON массивы (ближе к реальности)
```csv
messages,has_tz_context,trigger_type,source_tz,notes
"[""завтра в час"", ""а это по москве?""]",1,clarification_question,Europe/Moscow,
"[""давай в 15:00 Мск""]",1,explicit_tz,Europe/Moscow,
```
**Плюсы:** Реальный контекст диалога
**Минусы:** Сложнее собирать, нужен парсинг JSON

### Рекомендация: Начать с Option A
- 80% кейсов — explicit_tz в одном сообщении ("16:30 Мск")
- 20% кейсов — clarification questions (можно добавить позже)
- Проще собрать, быстрее итерировать

---

## Integration Flow (target state)

```
Message[n]
  │
  ├─► TimeClassifier.predict() ─► has_time?
  │                                   │
  │                                   no ──► stop
  │                                   │
  │                                  yes
  │                                   │
  └─► TzContextTrigger.detect(message, recent_messages[-5:])
        │
        ├─► trigger_type = "none" ──► use user's verified TZ as source
        │
        ├─► trigger_type = "explicit_tz"
        │     │
        │     └─► regex extract (Мск → Europe/Moscow)
        │           │
        │           └─► source_tz resolved
        │
        └─► trigger_type = "clarification_question"
              │
              └─► LLM Agent с контекстом:
                    {
                      "messages": [...последние 5...],
                      "detected_times": [...],
                      "user_tz": "Asia/Tbilisi",
                      "chat_users_tzs": ["Europe/Moscow", "Asia/Tbilisi"]
                    }
                    │
                    └─► {source_tz: "Europe/Moscow", confidence: 0.95}

  │
  ▼
parse_times(text) with resolved source_tz
  │
  ▼
TimeConversion: source_tz → team timezones
```

---

## Key Patterns to Support

| Pattern | Example | Trigger Type | Priority |
|---------|---------|--------------|----------|
| Time + RU abbrev | "16:30 Мск" | explicit_tz | P0 |
| Time + "по" city | "15:00 по Тбилиси" | explicit_tz | P0 |
| TZ question | "это по москве?" | clarification_question | P0 |
| Time + EN abbrev | "3pm PST" | explicit_tz | P0 (already works) |
| Asking TZ | "какая таймзона?" | clarification_question | P1 |
| Range + TZ | "16:30+ Мск" | explicit_tz | P1 |
| Conflict (future) | user=Tbilisi, mentions Moscow | conflict | P2 |

---

## Open Questions

- [x] **Сколько сообщений назад смотреть?** → Начнём с 5 или по времени (5 минут)
- [x] **Формат датасета?** → Option A (отдельные фразы) для начала
- [ ] **Минимальный accuracy?** → 90% для Phase 1
- [ ] **Как обрабатывать конфликт user_tz ≠ mentioned_tz?** → mentioned = source, user = один из targets
- [ ] **UI для chat settings?** → bot commands достаточно для MVP
