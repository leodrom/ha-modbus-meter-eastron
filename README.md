# modbus_meter_eastron

Home Assistant custom integration for reading Eastron SDM power meters over
Modbus TCP, without the failure mode of the built-in `modbus:` platform.

## Why

The built-in `modbus:` integration polls every device on a gateway (MTU) in
one batch. If one slave is dead or not yet wired up, its per-register
timeout+retry storm stalls the whole cycle and takes every other meter on
the same RS485 bus down with it — in practice, adding one meter that isn't
physically connected yet can knock out readings for a dozen meters that are
working fine.

This integration polls each device through one shared connection per MTU,
but isolates failures per device:

- **MTU unreachable** (can't connect at all) → every device on that MTU is
  `unavailable`, no stale cached values are served.
- **MTU reachable, one device isn't answering** → that device is probed
  first by reading its S/N register alone (one request). If the probe
  fails, only that device goes `unavailable` — its other ~15-37 registers
  aren't even attempted that cycle, and every other device on the bus keeps
  updating normally.

This makes it safe to list meters that aren't physically connected yet in
your config — they just sit at `unavailable` instead of breaking the bus
for everyone else.

## Features

- Per-device failure isolation (see above) — a dead/unplugged meter costs
  one timeout per poll cycle, not one per register, and never affects its
  neighbours on the same Modbus bus.
- One persistent `AsyncModbusTcpClient` connection per gateway, matching
  hardware (e.g. Waveshare Modbus TCP↔RS485 bridges) that only accepts a
  single active session.
- Automatic reconnect on transport-level errors (broken socket etc.), but
  *not* on a plain "slave didn't answer" — that's normal for an offline
  device and reconnecting would just disrupt every other device sharing the
  connection for no benefit.
- YAML configuration — no cloud, no account, nothing to click through. A
  read-only Config Flow turns each configured gateway into a real
  `ConfigEntry` purely so Home Assistant can show a proper
  gateway → meter device hierarchy under **Settings → Devices & Services**.
- Built-in register-map profiles for Eastron SDM72CT-M (3-phase) and
  SDM120M (1-phase); devices can also define sensors inline, or mix a
  profile with extra inline sensors.
- Per-sensor `scan_interval` override (e.g. poll a serial-number register
  once an hour while voltage/current poll every 15s).
- Entity IDs are fixed and predictable (`sensor.<device_id>_<key>`), so
  existing Lovelace cards, recorder excludes, and Grafana panels keep
  working if you're migrating off of the built-in `modbus:` platform.

## Requirements

- Home Assistant with `custom_components/` support (standard).
- `pymodbus>=3.6.6` (installed automatically from `manifest.json`).
- A Modbus TCP gateway/bridge in front of your RS485 meters (e.g.
  Waveshare RS485↔Ethernet/WiFi modules), or any Modbus TCP-capable meter.

## Installation

### HACS (custom repository)

1. HACS → the "⋮" menu (top right) → **Custom repositories**.
2. Add `https://github.com/leodrom/ha-modbus-meter-eastron`, category
   **Integration**.
3. Install "Modbus Meter Eastron", then restart Home Assistant.

### Manual

1. Copy `custom_components/modbus_meter_eastron/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

Either way, nothing shows up yet until you add YAML config (below) and
restart again — this integration has no UI setup form by design (see
[Config Flow](#config-flow--devices--services) below).

## Configuration

Everything lives under a single `modbus_meter_eastron:` key, either directly
in `configuration.yaml` or in a `packages/` file included from it. Structure
is **MTU** (the Modbus TCP gateway) → list of **devices** (meters on that
gateway's RS485 bus) → **sensors** (from a register-map profile, inline, or
both).

```yaml
modbus_meter_eastron:
  mtus:
    - name: hangar_mtu          # unique name, also used as the gateway's
                                 # Device Registry identifier
      ip: 192.168.0.115
      port: 502                 # optional, default 502
      timeout: 1                # optional, seconds per read, default 1
      scan_interval: 15         # optional, seconds between poll cycles, default 15
      delay: 100                # optional, ms between requests on this MTU, default 100
      devices:
        - address: 2            # required, Modbus slave/unit address
          device_id: hangar02    # required, unique — used to build entity_ids
                                  # (sensor.hangar02_voltage_l1, etc.) and as
                                  # the meter's Device Registry identifier
          type: eastron           # optional, free text, shown as "Manufacturer"
                                  # in Device info (capitalized)
          profile: sdm72ct_m      # optional, pulls the full register list
                                  # from profiles/eastron.yaml — see below
          model: SDM72CT-M        # optional, shown in Device info
          meter_number: "Ангар-02" # optional, used as the Device Registry
                                  # device name (falls back to device_id)
          location: "Шафа 1"      # optional, free text, not used by the
                                  # integration itself — handy if you want a
                                  # sensor.<device_id>_location value; add it
                                  # as an inline sensor if you need it exposed
          scan_interval: 15        # optional, per-device override
          delay: 100                # optional, per-device override (ms)
          sensors: []               # optional, inline sensors (see below);
                                    # merged with the profile's sensors if
                                    # both are given

        - address: 22
          device_id: hangar22
          type: eastron
          profile: sdm120m
          model: SDM120M
          meter_number: "Ангар-22"
```

### MTU fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | yes | — | Unique per MTU; also the coordinator name and Device Registry identifier for the gateway. |
| `ip` | yes | — | Gateway IP. |
| `port` | no | `502` | |
| `timeout` | no | `1` | Seconds. Per Modbus read, not per full poll cycle. |
| `scan_interval` | no | `15` | Seconds between poll cycles for this MTU (all its devices, subject to per-device/per-sensor overrides). |
| `delay` | no | `100` | Milliseconds slept between consecutive Modbus requests on this MTU's shared connection — keeps a slow RS485 bus / bridge from being flooded. |
| `devices` | yes | — | List of device definitions, see below. |

### Device fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `address` | yes | — | Modbus slave/unit address on the bus. |
| `device_id` | yes | — | Must be unique across the whole installation (not just this MTU) — it becomes the entity_id prefix and the Device Registry identifier. |
| `type` | no | `eastron` | Free text, shown (capitalized) as "Manufacturer" in Device info. |
| `profile` | no | — | Name of a profile from `profiles/*.yaml` (currently `sdm72ct_m`, `sdm120m`). |
| `model` | no | — | Free text, shown in Device info. |
| `meter_number` | no | `device_id` | Used as the device's display name in Device Registry. |
| `location` | no | — | Free text; not read anywhere by the integration itself. |
| `scan_interval` | no | inherits MTU's | Per-device override, seconds. |
| `delay` | no | inherits MTU's | Per-device override, ms. |
| `sensors` | no | `[]` | Inline sensor definitions, see below. Merged with `profile`'s sensors when both are present; at least one of `profile`/`sensors` must resolve to a non-empty sensor list. |

### Sensor fields (profile entries or inline `sensors:`)

| Field | Required | Default | Notes |
|---|---|---|---|
| `key` | yes | — | Becomes the entity_id suffix: `sensor.<device_id>_<key>`. |
| `register` | yes | — | Modbus register address, **PDU-based (0-indexed)** — i.e. what you'd pass to `pymodbus`/`mbpoll`, not the 1-indexed "40001-style" addresses some meter manuals use. |
| `input_type` | no | `input` | `input` (function 04) or `holding` (function 03). |
| `data_type` | yes | — | One of `float32`, `uint32`, `int32`, `uint16`, `int16`. Multi-register values are decoded big-endian. |
| `unit_of_measurement` | no | — | |
| `device_class` | no | — | Standard HA sensor device class. |
| `state_class` | no | — | e.g. `measurement`, `total_increasing`. |
| `scan_interval` | no | inherits device/MTU | Per-sensor override, seconds — e.g. poll a serial number register once an hour instead of every cycle. |

One sensor, `key: serial_number`, is special: if a device defines it (directly
or via a profile), it's used as the **liveness probe** — read alone, before
any other register, each poll cycle. See [Architecture](#architecture)
below.

### Built-in profiles

`custom_components/modbus_meter_eastron/profiles/eastron.yaml` ships two
profiles for Eastron meters (register map confirmed against the vendor
Modbus protocol docs and cross-checked with live meters):

- **`sdm72ct_m`** — 3-phase SDM72CT-M: per-phase voltage/current/active
  power/apparent power/reactive power/power factor, plus system totals
  (active/apparent/reactive power, power factor), import/export active +
  reactive energy, power demand (current + peak, system/import/export),
  frequency, and serial number.
- **`sdm120m`** — 1-phase SDM120M: voltage/current/active power/reactive
  power/apparent power/power factor, import/export active + reactive
  energy, power demand (current + peak), frequency, and serial number.

Open that file to see the exact `key`/`register`/`unit_of_measurement` list
for each — it's plain YAML, in the same shape as an inline `sensors:` list,
so you can copy entries out of it as a starting point for a custom profile
or a per-device override.

To add a profile for another meter model, add a new top-level key to
`profiles/eastron.yaml` (or drop another `*.yaml` file in `profiles/` — every
file in that directory is loaded and merged) with a list of sensor
definitions in the same shape.

### Entity IDs

Always `sensor.<device_id>_<key>` (e.g. `sensor.hangar02_voltage_l1`) —
deliberately not namespaced by domain or MTU, so it's a drop-in replacement
for entity IDs from the built-in `modbus:` platform if you're migrating.
Make sure `device_id` is unique across your whole config, not just within
one MTU.

## Config Flow / Devices & Services

There is no manual setup form. Configuration is YAML-only — the integration
still implements a Config Flow, but only an import step: on startup, each
configured MTU is silently turned into a `ConfigEntry` (`async_step_import`
in `config_flow.py`), and the "Add hub" button that Home Assistant shows for
any `integration_type: hub` will abort with a clear "configured via YAML
only" message if clicked.

This exists purely so Home Assistant's Device Registry has something to
attach devices to — a plain YAML/discovery platform without a `ConfigEntry`
can't own device records. The payoff: **Settings → Devices & Services**
shows a real hierarchy, one device for the MTU (gateway) itself (model
"Modbus TCP-RTU gateway", with the gateway's `ip:port` visible in Device
info) with every meter on that bus listed as a child device (`via_device`)
underneath it, each showing its Modbus address, model, and manufacturer.

## Architecture

One `ModbusMtuCoordinator` (a standard HA `DataUpdateCoordinator`) per MTU,
each holding one persistent `AsyncModbusTcpClient`. Every poll cycle:

1. If the client isn't connected, try to connect. **Failure here means the
   whole MTU is down** — the coordinator returns `{}` and every device on
   this bus goes `unavailable` immediately (no stale cached values served).
2. Otherwise, walk the configured devices in order. For each device that
   defines a `serial_number` sensor (directly or via profile), read *only*
   that register first as a liveness probe:
   - Probe fails → mark the device `unavailable` for this cycle and move on
     to the next device. None of its other ~15-37 registers are attempted —
     a dead/unplugged meter costs exactly one timeout per cycle, not one
     per register.
   - Probe succeeds → read the rest of the device's sensors normally, each
     in its own `try`/`except` (one bad register doesn't take down the
     others on the same device).
3. A device with no `serial_number` sensor at all can't be probed this way —
   every sensor is simply attempted and used as its own liveness check.
4. On an `OSError` (socket reset, broken pipe — a transport-level failure),
   the shared connection is closed and reconnected before the next read,
   since the TCP session itself is suspect. On a `ModbusException` /
   timeout (the slave just didn't answer — normal for an offline device),
   there's deliberately **no reconnect**, since that would disrupt every
   other device sharing the same connection for no benefit.

Float values are rounded to 2 decimal places before being exposed as sensor
state.

## Troubleshooting

- **Everything on one MTU is `unavailable`**: the gateway itself is
  unreachable (wrong IP/port, network issue, or the bridge is stuck — power
  cycle it). Check Home Assistant's log for
  `MTU %s (%s:%s) unreachable, all devices unavailable this cycle`.
- **One specific device is `unavailable`, others on the same MTU are fine**:
  that's the isolation working as intended — either the meter is genuinely
  offline/unplugged, or its wiring/address is wrong. Enable debug logging
  (below) to see the actual probe/read failure.
- **A gateway that only supports one active session drops everything when
  you poll it from two places at once** (e.g. an external `mbpoll` /
  diagnostic session running alongside Home Assistant) — don't run parallel
  diagnostics against the same gateway while HA is actively polling it.
- **Debug logging**:
  ```yaml
  logger:
    logs:
      custom_components.modbus_meter_eastron: debug
  ```
  This logs every probe/read failure per device/register, not just the
  cycle-level summary.
- **Slow/negative feedback loop after adding many new devices at once**: if
  a device is added to config before it's physically wired up, it's meant
  to just sit at `unavailable` — that's the whole point of this
  integration. If you see the *entire* MTU stall instead, that means the
  connect step itself (not a specific device) is failing — see the first
  bullet above.

## Known limitations

- Meter model/profile is explicit (`type`/`profile` in YAML) — there's no
  auto-detection of meter model over Modbus. (SDM120M documents a "meter
  code" holding register for this; SDM72CT-M's official protocol doc does
  not document an equivalent register, so auto-detect isn't reliable across
  both supported models.)
- `location` is accepted in config but not exposed anywhere by the
  integration itself — add it as an inline sensor (a static/template value)
  if you want it as an entity.
- No energy dashboard / Riemann-sum helpers are set up automatically —
  point Home Assistant's Energy dashboard at the relevant
  `total_increasing` energy sensors yourself.

## License

MIT — see [LICENSE](LICENSE).
