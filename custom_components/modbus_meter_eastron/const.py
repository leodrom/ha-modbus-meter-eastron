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

PROBE_KEY = "serial_number"
