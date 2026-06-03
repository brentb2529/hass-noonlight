# hass-noonlight — Home Assistant custom component for Noonlight dispatch

## What this is

A Home Assistant custom integration that exposes [Noonlight](https://www.noonlight.com)'s emergency-services dispatch API to HA users — primarily so anyone with an `alarm_control_panel.*` entity can wire a real police/fire/medical response into their HA automations without writing a single line of Python.

Distributed via HACS. Self-contained: no external dashboard or third-party service required.

## What this is not

- Not a dashboard. UI is whatever the user already has (Lovelace, B-Panels, etc.).
- Not coupled to any specific alarm panel integration (works with `manual_alarm`, Konnected, Ring, Envisalink, Hubitat-via-HA, custom MQTT panels, etc.).
- Not a multi-provider monitoring abstraction. Noonlight only. If RapidSOS/ADT support is wanted later, it's a separate component.

## Why a custom integration (not a script or AppDaemon app)

- Native config flow → users add it from the HA UI, not by editing `configuration.yaml`.
- Exposes entities (`binary_sensor`, `sensor`) that participate in dashboards and automations.
- Exposes services (`noonlight.dispatch_*`, `noonlight.cancel`) that other automations target.
- HACS distributable; lives where HA users expect security integrations to live.

## Repo layout

```
hass-noonlight/
├── custom_components/
│   └── noonlight/
│       ├── __init__.py           # async_setup_entry, config entry lifecycle
│       ├── manifest.json
│       ├── config_flow.py        # UI setup + reauth + options flow
│       ├── const.py
│       ├── coordinator.py        # DataUpdateCoordinator wrapping Noonlight API
│       ├── api.py                # thin async httpx wrapper around Noonlight
│       ├── binary_sensor.py      # dispatch_pending, dispatch_active
│       ├── sensor.py             # dispatch_state (enum), last_event
│       ├── services.py           # service registrations + handlers
│       ├── services.yaml         # service schemas for HA UI
│       ├── strings.json          # user-facing strings (config flow, etc.)
│       └── translations/
│           └── en.json
├── tests/
│   ├── conftest.py
│   ├── test_config_flow.py
│   ├── test_services.py
│   ├── test_dispatch_lifecycle.py
│   └── fixtures/
├── .github/workflows/
│   ├── validate.yml              # HA + HACS validation
│   └── tests.yml                 # pytest-homeassistant-custom-component
├── hacs.json
├── info.md                       # what HACS shows in its UI
├── README.md
├── LICENSE                       # MIT (HACS-default-friendly)
└── CHANGELOG.md
```

## Entities exposed

Per config entry (so multi-account/multi-residence setups work):

- `binary_sensor.noonlight_<account>_dispatch_pending` — `on` during the entry-delay grace window. Lovelace + automations watch this to show a "CANCEL" UI.
- `binary_sensor.noonlight_<account>_dispatch_active` — `on` after a dispatch fires, until cleared or canceled by Noonlight or by the user. Useful for "siren stays on while help is on the way" type automations.
- `sensor.noonlight_<account>_dispatch_state` — enum: `idle | pending | dispatched | canceled | error`. Single source of truth; the two binary sensors are derived from this.
- `sensor.noonlight_<account>_last_event` — ISO timestamp + event type of the most recent state transition. Surfaces nicely in history graphs.

State is held in `hass.data[DOMAIN][entry_id]`, persisted across restarts via the integration's storage helper (`Store`). Audit log entries write to the same Store and rotate at a configurable size.

## Services exposed

```yaml
# services.yaml
dispatch_police:
  description: Request police dispatch through Noonlight.
  fields:
    entry_delay_seconds:
      description: Grace window before the dispatch actually fires. Set 0 to skip.
      example: 30
      selector: { number: { min: 0, max: 120 } }
    account:
      description: Config entry id. Optional when only one account is configured.

dispatch_fire: { ... }
dispatch_medical: { ... }
dispatch_all: { ... }       # police + fire + medical in one alarm

cancel:
  description: Abort a pending dispatch, or signal Noonlight that an active dispatch is a false alarm.
  fields:
    reason:
      description: Free-text reason (audit log).
      example: "User entered correct disarm code"
    account: { ... }

test_dispatch:
  description: Fire a no-op round-trip against Noonlight's sandbox endpoint. Confirms credentials, network, and signing without alerting real responders.
```

## The dispatch lifecycle

```
idle ──dispatch_*──> pending ──(entry_delay timer fires)──> dispatched ──(cleared by user or Noonlight)──> idle
                       │
                       └──cancel──> canceled ──(2s settle)──> idle
```

1. `dispatch_*` service called → state goes `pending`, `binary_sensor.dispatch_pending` flips `on`, timer starts (default 30s, overridable per call).
2. If `cancel` is called before the timer fires → state goes `canceled`, no network call to Noonlight, audit log records the abort.
3. If timer expires → POST to Noonlight `/dispatch/v1/alarms`, state goes `dispatched`, `dispatch_active` flips `on`.
4. While `dispatched`, the component long-polls Noonlight's status endpoint (or subscribes to its WebSocket if available) and reflects status into `dispatch_state`.
5. `cancel` while `dispatched` → POST to Noonlight's cancel endpoint with the reason. Noonlight decides whether to actually stop responders; the component just reflects the API's response.

**De-dup window**: after a dispatch fires, subsequent `dispatch_*` calls within `dedupe_seconds` (default 300) are no-ops with a logged warning. Prevents an oscillating alarm from triggering ten dispatches in a minute.

## Recommended automation pattern (documentation, not code)

```yaml
automation:
  - alias: Intrusion → Noonlight police
    trigger:
      - platform: state
        entity_id: alarm_control_panel.home
        to: "triggered"
    action:
      - service: noonlight.dispatch_police
        data: { entry_delay_seconds: 30 }

  - alias: User disarmed during entry delay → cancel Noonlight
    trigger:
      - platform: state
        entity_id: alarm_control_panel.home
        to: "disarmed"
    condition: "{{ is_state('binary_sensor.noonlight_main_dispatch_pending', 'on') }}"
    action:
      - service: noonlight.cancel
        data: { reason: "Panel disarmed during entry delay" }
```

A Lovelace card example using `conditional` + `entity-button` to show the cancel button only while `dispatch_pending` is `on` goes in the README.

## Configuration (config flow)

Step 1 — credentials:
- `api_token` (Noonlight long-lived token; obtained from Noonlight account portal)
- `sandbox_mode` (boolean, default `true` for new installs — flipping to prod requires the user to re-acknowledge the safety disclosure)

Step 2 — caller info:
- `name`, `phone`, `address`, `city`, `state`, `zip` — passed to Noonlight on every dispatch as the location/contact

Step 3 — defaults:
- `default_entry_delay_seconds` (default 30, min 0, max 120)
- `dedupe_seconds` (default 300)
- `services_granted` — checkboxes for which `dispatch_*` services to register (lets users opt out of, say, medical)

Step 4 — safety acknowledgment:
- Explicit "I understand this integration can summon real police, fire, and medical responders, and that false dispatches may incur fines from local authorities" checkbox. Required to complete config flow when `sandbox_mode=false`.

**Reauth flow** triggers when the Noonlight API returns 401 — surfaces a Repair issue in HA and lets the user paste a new token without re-entering address/contact.

**Options flow** lets users adjust the entry delay, dedupe window, and granted services post-setup. Address changes require a fresh config entry (audit trail).

## Safety rails

| Rail | Implementation |
|---|---|
| Entry-delay grace window | Timer in the coordinator, cancelable via `cancel` service |
| Cancel UI hook | `binary_sensor.dispatch_pending` — UI is whatever the user has |
| Real-vs-sandbox separation | `sandbox_mode` flag picks API base URL (`api-sandbox.noonlight.com` vs `api.noonlight.com`) |
| De-dup | In-memory + persisted-to-Store dispatch timestamp per service |
| Audit log | Append-only file in `.storage/noonlight_audit_<entry_id>.jsonl` — every state transition, service call, API response |
| Test dispatch | `noonlight.test_dispatch` service that always hits sandbox even when `sandbox_mode=false` |
| Repair issues for failures | HA Repair items on auth failure, network failure, or unexpected Noonlight response shapes |

## Testing

- `pytest-homeassistant-custom-component` for unit + integration tests of the coordinator, services, and config flow.
- `aioresponses` to mock the Noonlight HTTP API. Tests assert: correct URLs, correct payloads, correct state transitions, correct audit entries.
- Live integration tests gated behind an env var (`NOONLIGHT_LIVE_TESTS=1`) that always hit sandbox, never prod. CI does not run these by default.
- Snapshot the config-flow user-facing strings (`strings.json`) to catch translation drift.

## HACS distribution prep

- `hacs.json` with `name`, `render_readme: true`.
- `manifest.json` with `domain: noonlight`, `version` semver, `requirements: ["httpx>=0.24"]`, `iot_class: cloud_polling` (or `cloud_push` if we adopt their WebSocket).
- `info.md` for the HACS card.
- README sections: install via HACS, config-flow walkthrough, example automations, example Lovelace card, safety disclosure, troubleshooting, link to upstream Noonlight docs.
- LICENSE: MIT (HACS-default-friendly).
- GitHub Actions: HA validate (`home-assistant/actions/hassfest`), HACS validate (`hacs/action`), pytest matrix on supported Python versions.

## Known consumers

- **B-Panels dashboard** ([github.com/brentb2529/B-Panels](https://github.com/brentb2529/B-Panels)) — a kiosk dashboard with native HA support landing in v2.0. It surfaces `binary_sensor.noonlight_*_dispatch_pending` in its alarm tile and uses the existing HA WebSocket stream to render a cancel button. No special code on the dashboard side; this component is just another HA integration to it.

## Out of scope

- A B-Panels-specific cancel UI. B-Panels gets the cancel signal via the binary_sensor like any other HA consumer.
- Non-Noonlight monitoring providers. Separate components if and when.
- Two-way voice with a Noonlight agent. Phone-only for now.
- Geocoding/address autocomplete in the config flow. Users paste plain text.

## References

- Noonlight Dispatch API: https://docs.noonlight.com/reference (and the OpenAPI spec they publish)
- HA developer docs — custom integrations: https://developers.home-assistant.io/docs/creating_integration_manifest
- HACS submission requirements: https://hacs.xyz/docs/publish/integration
- `pytest-homeassistant-custom-component`: https://github.com/MatthewFlamm/pytest-homeassistant-custom-component
