"""Binary sensor platform for modbus_meter_eastron: MTU gateway connectivity."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities: list[BinarySensorEntity] = [
        ModbusMtuOnlineBinarySensor(coordinator, data["mtu_name"])
    ]
    for device in data["devices"]:
        entities.append(ModbusMeterOnlineBinarySensor(coordinator, device))

    async_add_entities(entities)


class ModbusMtuOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Whether the MTU's Modbus TCP connection is currently reachable.

    Reads coordinator.mtu_online rather than relying on `available`
    (CoordinatorEntity's default) -- the coordinator never fails its own
    update (a dead MTU still returns {} successfully, see coordinator.py),
    so this entity would otherwise always report "on".
    """

    _attr_has_entity_name = True
    _attr_name = "Gateway online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, mtu_name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{mtu_name}_online"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, mtu_name)})

    @property
    def is_on(self) -> bool:
        return self.coordinator.mtu_online


class ModbusMeterOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Whether this meter answered its last S/N probe (coordinator.py PROBE_KEY).

    Independent of the meter's other sensors going unavailable (which
    already happens when the probe fails) -- this gives an explicit,
    dedicated online/offline signal for the meter as a device, matching the
    MTU's "Gateway online" sensor above.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device: dict) -> None:
        super().__init__(coordinator)
        device_id = device["device_id"]
        meter_number = device.get("meter_number", device_id)
        self._device_id = device_id
        # has_entity_name=False, self-contained name (like ModbusMeterSensor
        # in sensor.py) -- the device is already named after meter_number
        # (see sensor.py's DeviceInfo), so has_entity_name=True would double
        # it up as "<meter_number> <meter_number> Online".
        self._attr_name = f"{meter_number} online"
        # Fixed entity_id (like ModbusMeterSensor) rather than deriving one
        # from meter_number -- it's a Cyrillic value (e.g. "Ангар-02"), not
        # safe to slugify into an entity_id.
        self.entity_id = f"binary_sensor.{device_id}_online"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_online"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def is_on(self) -> bool:
        return self.coordinator.device_online.get(self._device_id, False)
