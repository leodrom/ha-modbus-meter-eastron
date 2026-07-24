"""modbus_meter_eastron: YAML-configured Modbus meter reader with per-device failure isolation.

See /opt/odoo/memory.ai/homeassistant--eastron.md for why this exists: the
built-in `modbus:` platform lets one dead/unplugged slave's read timeouts
stall the whole gateway's scan cycle. Here every device on an MTU (gateway)
is polled through one shared connection; each device is probed first by
reading its S/N register alone, and only its other registers are attempted
if that probe succeeds -- so a dead device costs one timeout, not one per
register, and never blocks its neighbours on the same bus.
"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .config_schema import CONFIG_SCHEMA, load_profiles, resolve_device_sensors
from .const import DOMAIN, PLATFORM
from .coordinator import ModbusMtuCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = ["CONFIG_SCHEMA"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    domain_config = config[DOMAIN]
    # load_profiles() does blocking file I/O (os.listdir/open) -- keep it off the event loop
    profiles = await hass.async_add_executor_job(load_profiles)

    hass.data.setdefault(DOMAIN, {})
    mtus_discovery: list[dict] = []

    for mtu_conf in domain_config["mtus"]:
        devices = []
        for device_conf in mtu_conf["devices"]:
            device = dict(device_conf)
            device["sensors"] = resolve_device_sensors(device_conf, profiles)
            devices.append(device)

        coordinator = ModbusMtuCoordinator(hass, mtu_conf, devices)
        # Deliberately NOT awaited: an MTU with slow/dead devices can take
        # much longer than HA's setup budget to complete a full first poll
        # (that's the exact failure mode this integration replaces). Let HA
        # finish starting up; entities show unavailable until this first
        # refresh lands.
        hass.async_create_task(coordinator.async_refresh())

        hass.data[DOMAIN][mtu_conf["name"]] = coordinator
        mtus_discovery.append({"name": mtu_conf["name"], "coordinator": coordinator, "devices": devices})

        _LOGGER.info(
            "modbus_meter_eastron: MTU '%s' (%s:%s) set up with %d device(s)",
            mtu_conf["name"],
            mtu_conf["ip"],
            mtu_conf["port"],
            len(devices),
        )

    hass.async_create_task(
        discovery.async_load_platform(hass, PLATFORM, DOMAIN, {"mtus": mtus_discovery}, config)
    )

    return True
