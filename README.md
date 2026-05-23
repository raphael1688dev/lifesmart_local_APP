# LifeSmart Local Integration for Home Assistant

Control your LifeSmart devices locally through Home Assistant without cloud dependency.

## Features
- Local control of LifeSmart devices (UDP, port 12348)
- Real-time push state synchronization
- Switches, curtain covers, IR remotes, temperature & battery sensors
- No cloud connection required
- Target environment: Home Assistant 2026.5+

## Installation

1. Copy the `lifesmart` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for **Local LifeSmart**

> **Upgrading from a previous build that used the `lls` domain:**
> Remove the old integration entry first, then add the new `lifesmart` integration.
> Old `lls_*` entity registry entries become orphans and should be deleted.

## Configuration

You'll need:
- Hub IP address
- Model number (found on hub)
- Token (found in LifeSmart app)

## Supported Devices

### Switches (`switch` platform)
Toggle channels `L1`/`L2`/`L3`:
- `SL_SW_NS1` / `SL_SW_NS2` / `SL_SW_NS3` — Moonstone Switch (§6.3.4)
- `SL_SW_ND1` / `SL_SW_ND2` / `SL_SW_ND3` — Stellar/Starry/Polar Switch (§6.3.2)
- `SL_SW_IF1` / `SL_SW_IF2` / `SL_SW_IF3` — Traditional Switch (§6.3.1)
- `SL_SW_RC` — Traditional Switch (§6.3.1)
- `SL_NATURE` — Nature Mini (as switch) (§6.3.9)

### Sensors (`sensor` platform)
- **Temperature** — `SL_NATURE` `T` channel (firmware exposes T even though spec lists only L*; raw value ÷ 10 = °C)
- **Battery** — channel `V` on `SL_SW_ND*` / `SL_MC_ND*` (§6.3.2 / §6.3.5); channel `P8` on `SL_P` MINS Curtain (§6.4.3). Range 0–100 %, with `SensorDeviceClass.BATTERY`.

### Cover (`cover` platform)
- `SL_P` — MINS Curtain Motor Controller (§6.4.3)

### Remote (`remote` platform)
- `SL_SPOT_NEW_V*` — SPOT IR remote, dynamic key discovery

## Usage

After setup, your devices will automatically appear in Home Assistant. The integration maintains push-based state synchronization between:
- Home Assistant controls
- Physical switch changes
- LifeSmart mobile app controls

## Changelog

### 20260523r0 — 2026-05-23
- **Battery sensor support extended** to Stellar/Starry/Polar Switches (`SL_SW_ND*`) and Multi-control Accessories (`SL_MC_ND*`), reading the `V` channel per Local Interfaces §6.3.2 / §6.3.5.
- **Bug fix:** `LifeSmartBatterySensor` was hard-coded to read `data["P8"]`; now reads `data[idx]`, so it works correctly across `P8` (MINS Curtain) and `V` (switches).
- **HA 2026.5 naming compliance:** `_attr_name` on temperature and battery sensors no longer duplicates the device name. HA composes the visible name from `DeviceInfo.name` + the function-only `_attr_name`, so existing UI labels remain the same.
- Added `SensorDeviceClass.BATTERY` / `SensorDeviceClass.TEMPERATURE` and `SensorStateClass.MEASUREMENT` for proper icons, low-battery warnings, and statistics graphs.

### 20260518r0 — 2026-05-18
- **R6 revert of R5 parallel-install scheme.** Folder `custom_components/lls/` → `custom_components/lifesmart/`; domain `lls` → `lifesmart`; all `lls_` prefixes removed from `unique_id` / `entity_id`. The integration now replaces (rather than coexists with) older LifeSmart installations.

## Troubleshooting

Common fixes:
1. Ensure hub is on the same network
2. Check hub IP address is correct
3. Verify token is entered correctly
4. Confirm hub model number matches
5. After upgrading from an `lls` build: remove the old integration entry before adding the new one

## Contributing

Found a bug or want to contribute? Visit our GitHub repository.

## License

This project is licensed under the MIT License.

## File Structure

<pre>
custom_components/lifesmart/
├── __init__.py
├── api.py
├── config_flow.py
├── const.py
├── cover.py
├── manifest.json
├── remote.py
├── sensor.py
├── services.yaml
├── switch.py
├── brand/
│   ├── icon.png
│   └── logo.png
└── translations/
    └── en.json
</pre>
