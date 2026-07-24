"""Read-only import flow: turns each YAML-configured MTU into a real ConfigEntry.

There's no user-facing setup form -- configuration stays in YAML (see
config_schema.py) exactly as before. This flow only exists so each MTU gets
a ConfigEntry, which is what makes Home Assistant show the MTU -> meter
device hierarchy in Settings -> Devices & Services (a plain YAML/discovery
platform, with no ConfigEntry, can't own Device Registry entries).
"""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class ModbusMeterEastronConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Import-only config flow, one entry per MTU defined in YAML."""

    VERSION = 1

    async def async_step_import(self, import_data: dict) -> Any:
        await self.async_set_unique_id(import_data["name"])
        self._abort_if_unique_id_configured(updates=import_data)
        return self.async_create_entry(title=import_data["name"], data=import_data)
