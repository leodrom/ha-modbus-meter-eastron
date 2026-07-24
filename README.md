# modbus_meter_eastron

Home Assistant custom integration for reading Eastron SDM power meters over
Modbus TCP, without the failure mode of the built-in `modbus:` platform.

## Why

The built-in `modbus:` integration polls every device on a gateway (MTU) in
one batch. If one slave is dead or not yet wired up, its per-register
timeout+retry storm stalls the whole cycle and takes every other meter on
the same RS485 bus down with it. This integration polls each device through
one shared connection per MTU, but isolates failures per device:

- **MTU unreachable** (can't connect at all) -> every device on that MTU is
  `unavailable`, no stale cached values are served.
- **MTU reachable, one device isn't answering** -> that device is probed
  first by reading its S/N register alone (one request). If the probe
  fails, only that device goes `unavailable` -- its other ~15-37 registers
  aren't even attempted that cycle, and every other device on the bus keeps
  updating normally.

This makes it safe to list meters that aren't physically connected yet in
your config -- they just sit at `unavailable` instead of breaking the bus
for everyone else.

## Config

YAML-only, no config flow. Structure: MTU (gateway) -> devices (address on
the bus) -> sensors (from a register-map profile or inline).

```yaml
modbus_meter_eastron:
  mtus:
    - name: my_mtu
      ip: 192.168.0.115
      port: 502
      timeout: 1          # seconds, per read
      scan_interval: 15   # seconds
      delay: 100           # ms between requests on this MTU
      devices:
        - address: 2       # Modbus slave address
          device_id: meter02
          type: eastron
          profile: sdm72ct_m   # or sdm120m -- see profiles/eastron.yaml
          model: SDM72CT-M
          meter_number: "Meter 02"
          location: "Cabinet 1"
```

`profile` pulls a full register list from `profiles/eastron.yaml`
(currently `sdm72ct_m` for the 3-phase meter and `sdm120m` for the 1-phase
one). A device can also define `sensors:` inline instead of, or in addition
to, a profile.

Entities are created for every configured sensor regardless of whether the
device has ever answered -- they just report `unavailable` until the S/N
probe succeeds.

## Requirements

- `pymodbus>=3.6.6`
- Home Assistant with `custom_components/` support (standard)
