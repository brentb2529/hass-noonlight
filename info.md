# Noonlight for Home Assistant

Wire real **police / fire / medical** dispatch into your Home Assistant
automations through [Noonlight](https://www.noonlight.com) — no Python required.

- Native config flow (no YAML).
- A cancelable **entry-delay** grace window so a disarm aborts the dispatch.
- `binary_sensor` + `sensor` entities for dashboards and automations.
- `noonlight.dispatch_police` / `dispatch_fire` / `dispatch_medical` /
  `dispatch_all` / `cancel` / `test_dispatch` services.
- **Sandbox** environment for safe testing — never alerts real responders until
  you opt into production and acknowledge the disclosure.
- Append-only audit log of every state change and API call.

> ⚠️ This integration can summon real emergency responders. Read the safety
> section of the README before switching to the production environment.
