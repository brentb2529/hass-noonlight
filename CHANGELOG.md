# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

Initial scaffold.

### Added
- Config flow: credentials + selectable environment (`production` / `sandbox` /
  `custom` base URL), caller info, defaults, and a production-only safety
  acknowledgment.
- Reauth flow on `401` and an options flow for entry delay, de-dup window, and
  granted services.
- `DataUpdateCoordinator` owning the dispatch state machine, cancelable
  entry-delay timer, per-service de-dup, Store persistence, and an append-only
  audit log.
- Entities: `binary_sensor.*_dispatch_pending`, `binary_sensor.*_dispatch_active`,
  `sensor.*_dispatch_state` (enum), `sensor.*_last_event` (timestamp).
- Services: `dispatch_police`, `dispatch_fire`, `dispatch_medical`,
  `dispatch_all`, `cancel`, `test_dispatch` (always sandbox).
- HA Repair issues on auth, network, and unexpected-response failures.
- HACS packaging, CI (hassfest + HACS validation, pytest matrix), and tests.

[Unreleased]: https://github.com/brentb2529/hass-noonlight/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/brentb2529/hass-noonlight/releases/tag/v0.1.0
