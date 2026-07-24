"""Sensor platform for modbus_meter_eastron, populated from a ConfigEntry (see __init__.py)."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    mtu_name = data["mtu_name"]

    entities: list[ModbusMeterSensor] = []
    for device in data["devices"]:
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device["device_id"])},
            name=device.get("meter_number", device["device_id"]),
            manufacturer=device.get("type", "").capitalize() or None,
            model=device.get("model"),
            via_device=(DOMAIN, mtu_name),
        )
        for sensor_def in device["sensors"]:
            entities.append(
                ModbusMeterSensor(coordinator, device["device_id"], sensor_def, device_info)
            )

    async_add_entities(entities)


class ModbusMeterSensor(CoordinatorEntity, SensorEntity):
    """One register of one meter. Value comes from the MTU's shared coordinator."""

    _attr_has_entity_name = False

    def __init__(self, coordinator, device_id: str, sensor_def: dict, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._key = sensor_def["key"]
        slug = f"{device_id}_{self._key}"

        # Fixed entity_id: this replaces the built-in `modbus:` platform 1:1,
        # existing Lovelace cards / recorder excludes / Grafana panels all
        # reference sensor.<device_id>_<key> directly and must keep working
        # unchanged.
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = f"{DOMAIN}_{slug}"
        self._attr_name = slug
        self._attr_native_unit_of_measurement = sensor_def.get("unit_of_measurement")
        self._attr_device_class = sensor_def.get("device_class")
        self._attr_state_class = sensor_def.get("state_class")
        self._attr_device_info = device_info

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._device_id, {}).get(self._key)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self._key in (self.coordinator.data or {}).get(self._device_id, {})
