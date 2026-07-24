"""Per-MTU Modbus polling with per-device failure isolation.

One AsyncModbusTcpClient connection is kept open per MTU (Modbus TCP<->RS485
gateway; the WaveShare bridges used here only accept a single active
session), and devices on that bus are polled sequentially through it.

Two levels of isolation, per the spec:
  - MTU unreachable (can't even connect) -> every device on that bus is
    unavailable, no stale cached values are kept.
  - MTU reachable but one device doesn't answer -> only that device is
    unavailable; probed first by reading its S/N register alone (cheap, one
    request) before attempting its other ~20-37 registers, so a dead device
    costs one timeout instead of one timeout per register.

See /opt/odoo/memory.ai/homeassistant--eastron.md for why this exists.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import PROBE_KEY

_LOGGER = logging.getLogger(__name__)

DATATYPE_WORDS = {
    "float32": 2,
    "uint32": 2,
    "int32": 2,
    "uint16": 1,
    "int16": 1,
}


class ModbusMtuCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls every device on one Modbus MTU (gateway), isolating failures per device."""

    def __init__(self, hass: HomeAssistant, mtu: dict, devices: list[dict]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"modbus_meter_eastron_{mtu['name']}",
            update_interval=timedelta(seconds=mtu["scan_interval"]),
        )
        self.mtu_name = mtu["name"]
        self._ip = mtu["ip"]
        self._port = mtu["port"]
        self._timeout = mtu["timeout"]
        self._default_delay_ms = mtu["delay"]
        self.devices = devices  # [{device_id, address, sensors: [...]}]
        self._client: AsyncModbusTcpClient | None = None
        self._last_read: dict[tuple[str, str], float] = {}
        self._unavailable_streak: dict[str, int] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        if self._client is None:
            self._client = AsyncModbusTcpClient(
                self._ip,
                port=self._port,
                timeout=self._timeout,
                retries=0,
                name=self.mtu_name,
            )

        if not self._client.connected:
            connected = await self._client.connect()
            if not connected:
                _LOGGER.warning(
                    "modbus_meter_eastron: MTU %s (%s:%s) unreachable, all devices unavailable this cycle",
                    self.mtu_name,
                    self._ip,
                    self._port,
                )
                # MTU itself is down: every device on the bus is genuinely
                # unavailable, not just "no fresh data" -- don't keep serving
                # stale cached values as if the bus were still healthy.
                return {}

        return await self._poll_devices()

    async def _reconnect(self) -> None:
        """Force a fresh TCP session after a transport-level read error."""
        if self._client is None:
            return
        self._client.close()
        if not await self._client.connect():
            _LOGGER.warning(
                "modbus_meter_eastron: reconnect to MTU %s (%s:%s) failed",
                self.mtu_name,
                self._ip,
                self._port,
            )

    async def _poll_devices(self) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        now = time.monotonic()

        for device in self.devices:
            device_id = device["device_id"]
            address = device["address"]
            delay = device.get("delay", self._default_delay_ms) / 1000

            probe_sensor = next((s for s in device["sensors"] if s["key"] == PROBE_KEY), None)
            if probe_sensor is not None:
                probe_value = await self._read_register(address, probe_sensor)
                await asyncio.sleep(delay)
                if probe_value is None:
                    self._mark_unavailable(device_id, address)
                    continue
                device_values = {PROBE_KEY: probe_value}
                self._last_read[(device_id, PROBE_KEY)] = now
            else:
                # no S/N in this device's sensor list -- can't probe, fall
                # back to reading every sensor as its own liveness check
                device_values = {}

            any_ok = probe_sensor is not None
            for sensor in device["sensors"]:
                key = sensor["key"]
                if key == PROBE_KEY and probe_sensor is not None:
                    continue  # already read above as the probe

                interval = sensor.get("scan_interval") or self.update_interval.total_seconds()
                last = self._last_read.get((device_id, key), 0.0)
                if now - last < interval:
                    prev = (self.data or {}).get(device_id, {}).get(key)
                    if prev is not None:
                        device_values[key] = prev
                    continue

                value = await self._read_register(address, sensor)
                await asyncio.sleep(delay)
                self._last_read[(device_id, key)] = now
                if value is not None:
                    device_values[key] = value
                    any_ok = True

            if any_ok:
                self._unavailable_streak[device_id] = 0
                results[device_id] = device_values
            else:
                self._mark_unavailable(device_id, address)

        return results

    def _mark_unavailable(self, device_id: str, address: int) -> None:
        streak = self._unavailable_streak.get(device_id, 0) + 1
        self._unavailable_streak[device_id] = streak
        if streak in (1, 5, 30):
            _LOGGER.info(
                "modbus_meter_eastron: device %s (address %s on %s) unavailable, "
                "%d consecutive cycles",
                device_id,
                address,
                self.mtu_name,
                streak,
            )

    async def _read_register(self, address: int, sensor: dict) -> float | int | None:
        word_count = DATATYPE_WORDS[sensor["data_type"]]
        try:
            if sensor.get("input_type", "input") == "holding":
                response = await self._client.read_holding_registers(
                    sensor["register"], count=word_count, device_id=address
                )
            else:
                response = await self._client.read_input_registers(
                    sensor["register"], count=word_count, device_id=address
                )
        except OSError as err:
            # Transport-level failure (socket reset, broken pipe, etc.) --
            # the shared TCP session itself is bad, not just this one slave.
            # Reconnect so the next read (this device or the next one) gets
            # a fresh session.
            _LOGGER.debug(
                "modbus_meter_eastron: %s address %s '%s' socket error: %s -- reconnecting",
                self.mtu_name,
                address,
                sensor["key"],
                err,
            )
            await self._reconnect()
            return None
        except (ModbusException, asyncio.TimeoutError) as err:
            # Protocol-level "slave didn't answer" -- normal for an offline
            # device, the TCP session to the MTU itself is still fine, so
            # don't reconnect (that would just disrupt every other device
            # sharing this connection for no benefit).
            _LOGGER.debug(
                "modbus_meter_eastron: %s address %s '%s' read failed: %s",
                self.mtu_name,
                address,
                sensor["key"],
                err,
            )
            return None

        if response is None or response.isError():
            return None

        try:
            dtype = self._client.DATATYPE[sensor["data_type"].upper()]
            value = self._client.convert_from_registers(response.registers, dtype, word_order="big")
        except Exception as err:  # noqa: BLE001 - never let a decode edge-case kill the cycle
            _LOGGER.debug("modbus_meter_eastron: decode failed for '%s': %s", sensor["key"], err)
            return None

        return round(value, 2) if isinstance(value, float) else value
