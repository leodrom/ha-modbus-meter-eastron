"""YAML schema + register-map profile loading for modbus_meter_eastron."""
from __future__ import annotations

import os

import voluptuous as vol
import yaml

import homeassistant.helpers.config_validation as cv

from .const import (
    DATA_TYPES,
    DEFAULT_DELAY_MS,
    DEFAULT_PORT,
    DEFAULT_RETRIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    INPUT_TYPES,
)

PROFILES_DIR = os.path.join(os.path.dirname(__file__), "profiles")

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required("key"): cv.string,
        vol.Required("register"): cv.positive_int,
        vol.Optional("input_type", default="input"): vol.In(INPUT_TYPES),
        vol.Required("data_type"): vol.In(DATA_TYPES),
        vol.Optional("unit_of_measurement"): cv.string,
        vol.Optional("device_class"): cv.string,
        vol.Optional("state_class"): cv.string,
        vol.Optional("scan_interval"): vol.Coerce(float),
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required("address"): cv.positive_int,
        vol.Required("device_id"): cv.string,
        vol.Optional("type", default="eastron"): cv.string,
        vol.Optional("profile"): cv.string,
        vol.Optional("model"): cv.string,
        vol.Optional("meter_number"): cv.string,
        vol.Optional("location"): cv.string,
        vol.Optional("scan_interval"): cv.positive_int,
        vol.Optional("delay"): vol.Coerce(float),
        vol.Optional("sensors", default=[]): [SENSOR_SCHEMA],
    }
)

MTU_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("ip"): cv.string,
        vol.Optional("port", default=DEFAULT_PORT): cv.port,
        vol.Optional("timeout", default=DEFAULT_TIMEOUT): vol.Coerce(float),
        vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
        vol.Optional("delay", default=DEFAULT_DELAY_MS): vol.Coerce(float),
        vol.Optional("retries", default=DEFAULT_RETRIES): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Required("devices"): [DEVICE_SCHEMA],
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({vol.Required("mtus"): [MTU_SCHEMA]}),
    },
    extra=vol.ALLOW_EXTRA,
)


def load_profiles() -> dict[str, list[dict]]:
    """Load every *.yaml file under profiles/ and merge their top-level keys."""
    profiles: dict[str, list[dict]] = {}
    if not os.path.isdir(PROFILES_DIR):
        return profiles
    for fname in sorted(os.listdir(PROFILES_DIR)):
        if not fname.endswith((".yaml", ".yml")):
            continue
        with open(os.path.join(PROFILES_DIR, fname), encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        for profile_name, sensors in data.items():
            profiles[profile_name] = [SENSOR_SCHEMA(sensor) for sensor in sensors]
    return profiles


def resolve_device_sensors(device: dict, profiles: dict[str, list[dict]]) -> list[dict]:
    """Merge a device's profile register-map with any inline sensor overrides."""
    sensors: list[dict] = []
    profile_name = device.get("profile")
    if profile_name:
        if profile_name not in profiles:
            raise vol.Invalid(
                f"modbus_meter_eastron: unknown profile '{profile_name}' for device '{device['device_id']}'"
            )
        sensors.extend(profiles[profile_name])
    sensors.extend(device.get("sensors", []))
    if not sensors:
        raise vol.Invalid(
            f"modbus_meter_eastron: device '{device['device_id']}' has no sensors (missing profile/sensors)"
        )
    return sensors
