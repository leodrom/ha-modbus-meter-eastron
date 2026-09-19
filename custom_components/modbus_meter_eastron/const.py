DOMAIN = "modbus_meter_eastron"
PLATFORM = "sensor"

CONF_MTUS = "mtus"
CONF_DEVICES = "devices"
CONF_SENSORS = "sensors"
CONF_PROFILE = "profile"
CONF_TYPE = "type"
CONF_ADDRESS = "address"
CONF_DEVICE_ID = "device_id"
CONF_MODEL = "model"
CONF_METER_NUMBER = "meter_number"
CONF_LOCATION = "location"
CONF_DELAY = "delay"
CONF_RETRIES = "retries"
CONF_CT_RATIO = "ct_ratio"

CONF_KEY = "key"
CONF_REGISTER = "register"
CONF_INPUT_TYPE = "input_type"
CONF_DATA_TYPE = "data_type"

DATA_TYPES = ("float32", "uint32", "int32", "uint16", "int16")
INPUT_TYPES = ("input", "holding")

DEFAULT_PORT = 502
DEFAULT_TIMEOUT = 1
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_DELAY_MS = 100
DEFAULT_RETRIES = 3  # matches pymodbus's own AsyncModbusTcpClient default
DEFAULT_MANUFACTURER = "eastron"
DEFAULT_CT_RATIO = 1.0

PROBE_KEY = "serial_number"

# Sensor keys the meter reports directly regardless of any external current
# transformer -- voltage/power-factor/frequency don't scale with CT ratio,
# and serial_number is metadata, not a measurement. Every other numeric
# register (current/power/energy/demand) is measured on the CT's secondary
# side and needs multiplying by the device's `ct_ratio` to read true
# primary-side values when the meter's own physical CT-ratio setup (which
# pymodbus/Modbus can't read or write -- see
# /opt/odoo/memory.ai/homeassistant--eastron.md) hasn't been corrected.
CT_UNSCALED_KEYS = frozenset(
    {
        "voltage_l1",
        "voltage_l2",
        "voltage_l3",
        "voltage",
        "power_factor_l1",
        "power_factor_l2",
        "power_factor_l3",
        "total_power_factor",
        "power_factor",
        "frequency",
        PROBE_KEY,
    }
)
