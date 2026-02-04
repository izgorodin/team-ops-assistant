# Changelog

All notable changes to Team Ops Assistant.

## [Unreleased]

### Removed
- Deleted unused `journal/` directory (development journals)
- Deleted `plan-timezoneSignalDetection.prompt.md` (obsolete planning doc)
- Deleted `data/DATASET_README.md` (referenced removed ML datasets)

---

## 2026-02-04 - Repository Cleanup

### Removed
- `src/core/intent_classifier.py` - unused ML classifier (0% coverage)
- `src/core/location_change_trigger.py` - developed but never integrated
- `prompts/geo_classify.md` - unused prompt
- 10 ML data files from `data/` (pkl models, training CSVs, archive/)

### Changed
- Agent temperature reduced from 0.3 to 0.15 for reliable tool calling
- Session utilities centralized in `src/core/session_utils.py`
- Removed `REVERIFY_TIMEZONE` session goal (now uses flag in context)

### Added
- 6 complex integration tests for geo intent scenarios
- Debug logging in agent handler for session diagnostics
- Malformed tool call parsing fallback

---

## 2026-02-03 - Geo Intent & Relocation

### Added
- Geo intent classification with smart trigger routing (`eb84976`)
- "Arrived" relocation patterns for EN/RU (`bf76fc3`)
- UTC offset and source labels in time conversion output (`b17cb58`)

### Fixed
- Always try geocoding for "по [city]" pattern (`882094b`)
- LLM timeouts increased for NVIDIA API (`0b43995`)
- Malformed convert_time tool calls now parsed (`aa25c99`)

### Changed
- City normalization prompt extracted to file (`6a6ea44`)

---

## 2026-01-31 - Geocoding Improvements

### Added
- Geocode cities via geonames alternatenames (Cyrillic support) (`923cd58`)
- Russian dative case normalization (бобруйску → бобруйск)

### Fixed
- Use resolved source_tz instead of timezone_hint (#43)

---

## 2026-01-30 - Production Hardening

### Added
- Phase 3: Production hardening (#37)
- CI/CD Pipeline (#36)
- Railway deployment configuration (`bb85beb`)
- All prompts translated to English (#39)

### Changed
- Stage 2 code review improvements (#42)
- TZ context trigger and location change classifiers (#40)

---

## 2026-01-28 - Relocation Detection

### Added
- User timezone tracking & relocation improvements (`0bc27a9`)
- Relocation confirmation flow (rules-based, no LLM) (`ff97ef1`)
- State lifecycle with confidence decay (#13)

### Fixed
- LLM timeout with fallback geocoding (`294c58f`)

---

## 2026-01-26 - Multi-Platform Support

### Added
- Webhook endpoints for all platforms (`00543b5`)
- Platform connectors complete (`45e65bf`)
- Dynamic timezone list based on chat participants (#17)
- @bot mention trigger & UX improvements (#16)

### Fixed
- Add timezone to chat active_timezones in web verification (`453c95b`)

---

## 2026-01-25 - Architecture Refactoring

### Added
- ADR-003: State lifecycle and confidence decay (#10)
- ADR-002: Platform message abstraction
- Timezone onboarding with geonamescache (#9)
- TelegramPoller test coverage (#12)

### Fixed
- reply_to_message_id used wrong value (`cc1dda1`)
- Deprecated datetime.utcnow() replaced (#7)

### Changed
- Replace MessageHandler with Pipeline architecture (#6)

---

## 2026-01-24 - Core Features

### Added
- Session-based agent mode for timezone resolution (`038251e`)
- State lifecycle - confidence decay & city pick (#3)
- LLM circuit breaker and timeout handling (#2)
- Russian time pattern support (`8718175`)

### Fixed
- Timezone parsing and throttle improvements (#4)

---

## 2026-01-23 - Initial Architecture

### Added
- Extensible architecture with protocols (#1)
- TDD contract tests for target architecture
- LLM fallback for uncertain time detection
- ML time classifier with training data
- Comprehensive time parsing and e2e tests

### Documentation
- Architecture AS-IS/TO-BE with migration path
- Production deployment documented
