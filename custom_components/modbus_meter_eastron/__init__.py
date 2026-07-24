"""modbus_meter_eastron: YAML-configured Modbus meter reader with per-device failure isolation.

See /opt/odoo/memory.ai/homeassistant--eastron.md for why this exists: the
built-in `modbus:` platform lets one dead/unplugged slave's read timeouts
stall the whole gateway's scan cycle. Here every device on an MTU (gateway)
is polled through one shared connection; each device is probed first by
reading its S/N register alone, and only its other registers are attempted
if that probe succeeds -- so a dead device costs one timeout, not one per
register, and never blocks its neighbours on the same bus.

Configuration is YAML-only (config_schema.py). Each MTU still gets turned
into a real ConfigEntry via an import-only config flow (config_flow.py) --
not for user setup, just so Home Assistant can own Device Registry entries
for the MTU -> meter hierarchy in Settings -> Devices & Services.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .config_schema import CONFIG_SCHEMA, load_profiles, resolve_device_sensors
from .const import DOMAIN
from .coordinator import ModbusMtuCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = ["CONFIG_SCHEMA"]

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    for mtu_conf in config[DOMAIN]["mtus"]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=mtu_conf)
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    mtu_conf = entry.data
    # load_profiles() does blocking file I/O (os.listdir/open) -- keep it off the event loop
    profiles = await hass.async_add_executor_job(load_profiles)

    devices = []
    for device_conf in mtu_conf["devices"]:
        device = dict(device_conf)
        device["sensors"] = resolve_device_sensors(device_conf, profiles)
        devices.append(device)

    coordinator = ModbusMtuCoordinator(hass, mtu_conf, devices)
    # Deliberately NOT awaited: an MTU with slow/dead devices can take much
    # longer than HA's setup budget to complete a full first poll (that's
    # the exact failure mode this integration replaces). Let HA finish
    # starting up; entities show unavailable until this first refresh lands.
    hass.async_create_task(coordinator.async_refresh())

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "devices": devices,
        "mtu_name": mtu_conf["name"],
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, mtu_conf["name"])},
        name=mtu_conf["name"],
        manufacturer="WaveShare",
        model="Modbus TCP-RTU gateway",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "modbus_meter_eastron: MTU '%s' (%s:%s) set up with %d device(s)",
        mtu_conf["name"],
        mtu_conf["ip"],
        mtu_conf["port"],
        len(devices),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data is not None:
            await data["coordinator"].async_shutdown()
    return unload_ok
