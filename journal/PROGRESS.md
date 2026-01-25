# Progress Tracker

## Bootstrap Phase

### 2024-01-21: Initial Repository Skeleton

**Completed:**
- [x] Project configuration files
  - pyproject.toml (ruff, pytest config)
  - pyrightconfig.json (strict type checking)
  - .gitignore
  - requirements.txt
  - env.example
  - configuration.yaml

- [x] Core domain implementation
  - src/core/models.py - Pydantic models
  - src/core/time_parse.py - Rules-based time parsing
  - src/core/time_convert.py - Timezone conversion
  - src/core/timezone_identity.py - User TZ management
  - src/core/dedupe.py - Deduplication
  - src/core/handler.py - Message processing pipeline

- [x] Storage layer
  - src/storage/mongo.py - MongoDB operations with Motor

- [x] Web application
  - src/app.py - Quart application with lifecycle
  - src/web/routes_verify.py - Verification endpoints
  - src/web/verify_page.html - Vue.js verification page

- [x] Telegram connector (MVP)
  - src/connectors/telegram/inbound.py - Full implementation
  - src/connectors/telegram/outbound.py - Full implementation

- [x] Discord connector (skeleton)
  - src/connectors/discord/inbound.py - Normalization + fixtures
  - src/connectors/discord/outbound.py - Structure + TODOs

- [x] WhatsApp connector (skeleton)
  - src/connectors/whatsapp/inbound.py - Normalization + fixtures
  - src/connectors/whatsapp/outbound.py - Structure + TODOs

- [x] LLM integration templates
  - prompts/trigger_detect.md
  - prompts/parse_time.md
  - prompts/format_reply.md

- [x] Test suite
  - tests/test_settings.py
  - tests/test_core_handler.py
  - tests/test_verify_flow.py
  - tests/test_telegram_contract.py
  - tests/test_discord_contract.py
  - tests/test_whatsapp_contract.py

- [x] Documentation
  - docs/ONBOARDING.md
  - docs/RUNBOOK.md
  - docs/ARCHITECTURE.md
  - docs/API.md

- [x] Journal entries
  - journal/01_scope_assumptions.md
  - journal/02_repo_structure_and_quality_gates.md
  - journal/PROGRESS.md (this file)

- [x] Root files
  - run.sh (startup script)
  - README.md (updated with comprehensive docs)

**Validation:**
- [x] run.sh executes successfully
- [x] pytest passes offline (68 tests)
- [x] ruff check passes
- [x] pyright check passes

---

## 2026-01-22: Local Testing & Configuration

**Completed:**
- [x] Quality gates audit and validation
- [x] Fixed graceful shutdown (added Discord/WhatsApp close calls)
- [x] Fixed README.md broken link
- [x] Translated Russian comment in .pre-commit-config.yaml
- [x] Created docs/VISION.md (3-layer architecture vision)
- [x] Created journal/03_audit_report.md

**Configuration:**
- [x] NVIDIA NIM API configured (OpenAI-compatible)
  - Model: qwen/qwen3-next-80b-a3b-instruct
  - Base URL: https://integrate.api.nvidia.com/v1
- [x] MongoDB Atlas connected (M0 Free, AWS Paris)
- [x] Telegram Bot token configured
- [x] .env file created with all credentials

**Local Testing Results:**
- [x] Core time parsing works
- [x] Time conversion works (PST → ET, UK, JST)
- [x] NVIDIA LLM API responds correctly
- [x] MongoDB connection successful
- [x] Health endpoint returns {"status":"ok"}
- [x] Telegram webhook processes messages

---

## 2026-01-22: Production Deployment

**Completed:**

- [x] Deployed to Render (<https://team-ops-assistant.onrender.com>)
- [x] Telegram webhook configured with production URL
- [x] End-to-end testing with real Telegram messages

**Production Testing Results:**

- [x] "Let's meet at 3pm PST" → Converts to ET, UK, Tokyo, Sydney
- [x] "Let's meet at 5pm GMT" → Converts correctly
- [x] Health endpoint accessible on production

**Known Limitations (backlog):**

- [ ] Dash separator not supported (e.g., "14-30" needs "14:30")
- [ ] Russian time format not supported (e.g., "в 14")
- [ ] Bare number with timezone not supported (e.g., "13 GMT" needs "13:00 GMT")

---

## MVP Complete

The minimum viable product is deployed and functional:

- Telegram bot responds to time mentions
- Converts to team timezones (PST, ET, UK, Tokyo, Sydney)
- Rules-based parsing handles standard formats
- MongoDB stores user state
- Health endpoint for monitoring

---

## 2026-01-24: Architecture Migration & Repo Cleanup

**Completed (PR #6, PR #7):**

- [x] Pipeline architecture migration (handler.py → pipeline.py)
- [x] Orchestrator now uses Pipeline instead of MessageHandler
- [x] Fixed datetime.utcnow() deprecation → datetime.now(UTC)
- [x] Added architecture-analysis skill for refactoring safety
- [x] Unified AI agent config files (CLAUDE.md as single source of truth)
- [x] Cleaned up parent directory (removed stale .git, symlinks)
- [x] Documented run.sh limitations (webhooks need public URL)

**Documentation Updates:**

- [x] docs/ONBOARDING.md - Added "Local Development Limitations" section
- [x] run.sh - Added detailed comment header explaining purpose
- [x] CLAUDE.md - Added note about AI agent config file structure
- [x] .claude/skills/architecture-analysis/skill.md - NEW skill

**Key Learnings:**

- Behavior inventory BEFORE refactoring prevents lost side effects
- D1-D7 workflow must be completed for ALL review comments
- run.sh is useful for local dev (pytest, health checks) but not bot testing

---

## 2026-01-24: Local Development & Tunnel Mode

**Completed (PR #8):**

- [x] Added pyngrok for automatic ngrok tunnel creation
- [x] `./run.sh` now creates tunnel and registers Telegram webhook
- [x] Local bot testing without manual ngrok setup
- [x] Updated docs/ONBOARDING.md with tunnel mode instructions

---

## 2026-01-24: Timezone Onboarding Improvements

**Completed (PR #9):**

- [x] Switched from Nominatim API to geonamescache (offline city lookup)
- [x] Added city abbreviation support: NY, NYC, MSK, LA, SF, СПб
- [x] Multi-word city support: "New York", "Санкт Петербург"
- [x] Population-based priority (London UK > London Canada)
- [x] Confidence decay function `get_effective_confidence()`
- [x] 18 new tests for city lookup

---

## 2026-01-24: State Lifecycle & Relocation Detection

**Completed (PR #13 - implements ADR-003):**

- [x] **Phase 1: Confidence Decay Integration**
  - Fixed `TimezoneStateManager` to use `get_effective_confidence()` with decay
  - Added `REVERIFY_TIMEZONE` session goal for re-verification flow
  - Different prompts: onboarding ("Какой твой город?") vs re-verify ("Твоя таймзона всё ещё X?")
  - Handle "да"/"yes" confirmation to refresh confidence

- [x] **Phase 2: Relocation Detection**
  - `RelocationDetector` with regex patterns (EN + RU, past + future tense)
  - Patterns: "moved to", "relocated", "now in", "переехал", "перееду", "переезжаю"
  - `RelocationHandler` resets confidence to 0.0
  - Pipeline prioritizes relocation over time triggers
  - 19 new tests for relocation detection

**Known Limitations (MVP):**

- Only English and Russian supported
- False positives: "my friend moved to X" triggers detection
- Hyphenated cities partially captured ("Нью-Йорк" → "Нью")

**Documented upgrade path:** Regex → Regex+LLM → ML classifier → Always-on LLM

---

## 2026-01-25: AAIC Audit & Exceeds Expectations Improvements

**Completed:**

### Audit (Epic #19)
- [x] Comprehensive repo audit against AAIC test assignment requirements
- [x] **Audit result: PASS** - all core requirements satisfied
- [x] Created Epic #19 with 15 child issues across 4 phases
- [x] Created GitHub issue templates in `.github/issues/`

### Phase 1: Quick Wins (PR #35 - MERGED)
- [x] **#20**: Fixed pyright error (`SecretStr` wrapper in test_llm_integration.py)
- [x] **#21**: Fixed ruff warnings (7 errors → 0 in scripts/)
- [x] **#22**: Updated stale docs (Discord/WhatsApp now "fully implemented")
- [x] **#23**: Added `Makefile` with dev commands (`make test`, `make lint`, `make check`)
- [x] Added `journal/08_llm_provider_decision.md` documenting NVIDIA NIM choice
- [x] Added `render.yaml` for Render.com deployment
- [x] Added `tests/test_llm_integration.py` with proper skip markers for CI
- [x] Addressed all 5 Copilot review comments (D7 workflow)

### Phase 2: CI/CD Pipeline (PR #36 - OPEN)
- [x] **#24**: Added GitHub Actions workflow (`.github/workflows/ci.yml`)
  - lint job (ruff check + format)
  - typecheck job (pyright)
  - test job (pytest + coverage)
  - pre-commit job
- [x] **#25**: Added Codecov integration and coverage badge
- [x] **#26**: Pre-commit config already existed, added CI check
- [x] Added CI and coverage badges to README.md

### Labels Created
- `phase1` (Quick Wins)
- `phase2` (CI/CD)
- `dx` (Developer Experience)
- `ci` (CI/CD related)

**Remaining Phases (backlog):**

| Phase | Issues | Description |
|-------|--------|-------------|
| Phase 3 | #27, #28, #29, #30 | Production Hardening (health, logging, rate limits, security) |
| Phase 4 | #31, #32, #33, #34 | Feature Additions (Docker, OpenAPI, admin, Discord Gateway) |

---

## Future Improvements

1. ~~Extend time parsing patterns (dash, Russian, bare numbers)~~ Partially done in PR #9
2. Implement LLM fallback for edge cases
3. Add Discord connector implementation
4. Add WhatsApp connector implementation
5. ~~User timezone verification flow testing~~ Done in PR #9, #13
6. **Two-layer detection**: Regex + LLM confirmation for relocation (reduce false positives)
7. **ML relocation classifier**: Train on production data

---

## Notes

- All network calls are mocked in tests for offline execution
- LLM integration is interface-only in MVP; rules handle 90%+ of cases
- **All 4 connectors fully implemented:** Telegram, Discord, WhatsApp, Slack
- NVIDIA API replaces Together AI for LLM (Qwen3-Next-80B via NIM)
- Confidence decay: -0.01/day, threshold 0.7 (30 days to re-verify)
- **498 tests passing** as of 2026-01-25
- **pyright + ruff**: 0 errors, 0 warnings
