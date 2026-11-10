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
PLATFORMS = ["switch", "sensor", "binary_sensor", "button", "scene", "cover", "remote", "event", "light"]

# Hub model friendly names — LI §3.3.10 L1561-1576 (mgatype from cfg:getver).
# Used to populate DeviceInfo.model on the hub device.
HUB_MODEL_NAMES = {
    "LSJZX1K": "Smart Station / Smart Station Pro",
    "LSSSMINIV1": "Smart Station Mini",
    "LSNAMIV1": "NatureMini",
    "LSNAMIV3": "NatureMini Pro",
    "LSNAMIV4": "NatureMini L",
    "LSMGANAV1": "NatureMini S / Nature 7",
    "LSHI3518": "Old version of Smart Station",
    # Not in the spec's list. Reported by a DEFED hub on 2026-11-10 (firmware
    # 1.0.94p10, Linux 4.4.94); "DEFED Smart Station" is the name OpenDev 1.9
    # §2.3 uses for that hub family.
    "LSDEFED": "DEFED Smart Station",
}

# Command Types
CMD_GET = 1    # Query command
CMD_SET = 3    # Control command
CMD_GET_REPLY = 2  # LI §3.1 GET-REPLY (was misnamed CMD_REPORT "status report" before R28)
CMD_NOTIFY = 9 # Event notify (OpenDev event service)

# Value Types
VAL_TYPE_ONOFF = 0x80
VAL_TYPE_BRIGHTNESS = 1
VAL_TYPE_COLOR_TEMP = 2
VAL_TYPE_RGB = 3
