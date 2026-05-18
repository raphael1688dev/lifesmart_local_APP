"""Constants for LifeSmart API specification v1.9."""

DOMAIN = "lifesmart"
MANUFACTURER = "LifeSmart"

# API Constants
DEFAULT_MODEL = "OD_ALI_TECH"

# API Protocol Constants
API_TIMEOUT = 10  # seconds
API_PORT = 12348
API_VERSION = 1
REMARK = "JL"

# Supported Platforms (對應 HA 的實體類別)
PLATFORMS = ["switch", "sensor", "cover", "remote"]

# Command Types
CMD_GET = 1    # Query command
CMD_SET = 3    # Control command
CMD_REPORT = 2 # Status report
CMD_NOTIFY = 9 # Event notify (OpenDev event service)

# Value Types
VAL_TYPE_ONOFF = 0x80
VAL_TYPE_BRIGHTNESS = 1
VAL_TYPE_COLOR_TEMP = 2
VAL_TYPE_RGB = 3
