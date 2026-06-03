# hass-noonlight

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration that exposes [Noonlight](https://www.noonlight.com)'s
emergency-services dispatch API to Home Assistant. Wire a real **police / fire /
medical** response into your automations — without writing any Python.

Pairs naturally with any `alarm_control_panel.*` entity (`manual_alarm`,
Konnected, Ring, Envisalink, custom MQTT panels, …). It is **not** coupled to
any specific alarm integration.

> ⚠️ **This integration can summon real emergency responders.** False dispatches
> may incur fines from local authorities. Test with the **sandbox** or **dev**
> environment first. Switching to **production** requires acknowledging a safety
> disclosure. See [Safety](#safety).

---

## Features

- **Native config flow** — add it from the HA UI, no `configuration.yaml`.
- **Cancelable entry-delay window** — a disarm during the grace period aborts the
  dispatch with no network call to Noonlight.
- **Selectable environment** — `production`, `sandbox`, or a `custom` base URL.
  Only `production` reaches real responders; sandbox is Noonlight's testing
  instance.
- **Entities** for dashboards/automations (per config entry):
  | Entity | Purpose |
  |---|---|
  | `binary_sensor.noonlight_<account>_dispatch_pending` | `on` during the entry-delay window — drive a CANCEL UI. |
  | `binary_sensor.noonlight_<account>_dispatch_active` | `on` while a dispatch is live with Noonlight. |
  | `sensor.noonlight_<account>_dispatch_state` | Enum: `idle / pending / dispatched / canceled / error`. Source of truth. |
  | `sensor.noonlight_<account>_last_event` | Timestamp + type of the last state transition. |
  | `binary_sensor.noonlight_<account>_api_reachable` | `on` while the heartbeat confirms Noonlight is reachable + the token is valid. |
  | `sensor.noonlight_<account>_last_health_check` | Timestamp of the last successful heartbeat probe. |
- **Services**: `dispatch_police`, `dispatch_fire`, `dispatch_medical`,
  `dispatch_all`, `cancel`, `test_dispatch`. Dispatch services take an optional
  `instructions` field (free text for responders, e.g. which sensor tripped).
- **Heartbeat** — a periodic, side-effect-free check (default every 15 min) that
  raises a Repair issue *before* an emergency if your token or connectivity breaks.
- **Multi-property** — one entry per site; an optional site label is sent to
  Noonlight (as `owner_id` and in the responder instructions) so you can tell
  which property raised an alarm.
- **De-dup window** so an oscillating alarm can't fire ten dispatches a minute.
- **Audit log** — append-only `.storage/noonlight_audit_<entry_id>.jsonl` of every
  state change, service call, and API response.

## Install (HACS)

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/brentb2529/hass-noonlight` as an **Integration**.
3. Install **Noonlight**, then restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → Noonlight**.

## Configuration

The config flow walks four steps:

1. **Credentials** — your Noonlight API token and the **environment**
   (`sandbox` recommended to start). Choose `custom` to paste your own base URL.
2. **Caller & location** — name, phone, address, and an optional site label
   sent to Noonlight on every dispatch. Phone, state, and ZIP are validated and
   normalized here (e.g. `(202) 555-0142` → `+12025550142`, `va` → `VA`) so a
   bad value is caught now instead of failing at dispatch time.
3. **Defaults** — entry delay (0–120 s, default 30), de-dup window (default
   300 s), and which dispatch services are granted.
4. **Safety acknowledgment** — required only when the environment is
   `production`.

**Re-auth**: a `401` from Noonlight raises a Repair issue and lets you paste a
new token without re-entering your address. **Reconfigure**: edit caller,
address, or site label any time via the entry's **Reconfigure** action — no need
to delete and re-add. **Options**: adjust entry delay, de-dup window, granted
services, and the heartbeat interval.

## Example automations

```yaml
automation:
  - alias: Intrusion → Noonlight police
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door_glass_break
        to: "on"
    action:
      - service: noonlight.dispatch_police
        data:
          entry_delay_seconds: 30
          # Tell responders what tripped — templated from the trigger.
          instructions: "Triggered by {{ trigger.to_state.name }}"

  - alias: User disarmed during entry delay → cancel Noonlight
    trigger:
      - platform: state
        entity_id: alarm_control_panel.home
        to: "disarmed"
    condition: "{{ is_state('binary_sensor.noonlight_main_dispatch_pending', 'on') }}"
    action:
      - service: noonlight.cancel
        data: { reason: "Panel disarmed during entry delay" }

  - alias: Warn me if Noonlight becomes unreachable
    trigger:
      - platform: state
        entity_id: binary_sensor.noonlight_main_api_reachable
        to: "off"
        for: { minutes: 5 }
    action:
      - service: notify.mobile_app
        data:
          message: "Noonlight is unreachable — emergency dispatch may not work."
```

## Example Lovelace cancel button

Shows a CANCEL button only while a dispatch is pending:

```yaml
type: conditional
conditions:
  - entity: binary_sensor.noonlight_main_dispatch_pending
    state: "on"
card:
  type: button
  name: CANCEL NOONLIGHT DISPATCH
  icon: mdi:close-octagon
  tap_action:
    action: call-service
    service: noonlight.cancel
    data: { reason: "Canceled from dashboard" }
```

## The dispatch lifecycle

```
idle ──dispatch_*──> pending ──(entry-delay timer)──> dispatched ──(cleared)──> idle
                       │
                       └──cancel──> canceled ──(2s settle)──> idle
```

- `cancel` **before** the timer fires → no network call; the abort is logged.
- `cancel` **after** dispatch → posts a cancel to Noonlight; Noonlight decides
  whether responders are actually recalled.

## Safety

| Rail | How |
|---|---|
| Entry-delay grace window | Cancelable timer in the coordinator |
| Cancel UI hook | `binary_sensor.*_dispatch_pending` |
| Real-vs-test separation | `environment` selects the base URL |
| De-dup | Persisted per-service dispatch timestamps |
| Audit log | `.storage/noonlight_audit_<entry_id>.jsonl` |
| Test dispatch | `noonlight.test_dispatch` always hits sandbox |
| Failure surfacing | HA Repair issues on auth/network/unexpected errors |

## Troubleshooting

- **Repair issue "authentication failed"** → your token was rejected; use the
  re-auth prompt to paste a new one.
- **`test_dispatch` fails** → confirms a credential/connectivity problem without
  alerting responders. Check the token and the chosen base URL.
- **Dispatch seemingly ignored** → check the de-dup window; repeats inside it are
  intentionally suppressed (look for a warning in the logs).

## Blueprints

Ready-made automation blueprints wire an alarm panel straight to Noonlight —
import, pick your panel and dispatch type, done. Both support a cancelable
entry delay and auto-cancel when the panel is disarmed.

| Blueprint | Use it for | Import |
| --------- | ---------- | ------ |
| [Dispatch on alarm trigger](blueprints/automation/noonlight/noonlight_dispatch_on_alarm.yaml) | Any `alarm_control_panel` (Manual, AlarmDecoder, …) | [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fbrentb2529%2Fhass-noonlight%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fnoonlight%2Fnoonlight_dispatch_on_alarm.yaml) |
| [Dispatch on Alarmo trigger](blueprints/automation/noonlight/noonlight_dispatch_on_alarmo.yaml) | [Alarmo](https://github.com/nielsfaber/alarmo) — also names the triggering sensor(s) in the responder note | [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fbrentb2529%2Fhass-noonlight%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fnoonlight%2Fnoonlight_dispatch_on_alarmo.yaml) |

## Links

- Noonlight Dispatch API: <https://docs.noonlight.com/reference>
- HA custom integrations: <https://developers.home-assistant.io/docs/creating_integration_manifest>
- HACS publishing: <https://hacs.xyz/docs/publish/integration>

## License

[MIT](LICENSE)
