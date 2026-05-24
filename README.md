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
- **Signal strength** — `lDbm` common attribute on every device (§6.1), in dBm, diagnostic category.

### Binary sensors (`binary_sensor` platform)
- **Connectivity** — `stat` common attribute on every device (§6.1). Updates via NOTIFY push (§4) and 15-minute fallback poll. Diagnostic category.

### Buttons (`button` platform)
- **Hub Reboot** — `button.lifesmart_hub_reboot`, calls `cfg:reboot` (§3.3.10). `ButtonDeviceClass.RESTART` so HA UI requests confirmation before pressing.

### Scenes (`scene` platform)
- **Hub scenes** — automatically discovered via `obj=scene` GET (§3.3.5). Each scene with `cls in ("scene", "groupirc")` is exposed as an HA Scene; activation calls `obj=doscene` SET (§3.3.6).

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

### 20260523r4 — 2026-05-23 — Hub-level entities (R8 Phase 1)
- **Hub identity sensors** — 3 new diagnostic sensors (`sensor.lifesmart_hub_firmware`, `sensor.lifesmart_hub_os`, `sensor.lifesmart_hub_model`) populated from `cfg:getver` (LI §3.3.10). `mgatype` is mapped through a friendly-name table (`LSJZX1K` → "Smart Station / Smart Station Pro", etc.).
- **Hub reboot button** — `button.lifesmart_hub_reboot` (`ButtonDeviceClass.RESTART`, config category) calls `cfg:reboot`. HA UI shows the standard confirmation prompt before pressing.
- **Scenes** — discovered via `obj=scene` GET and exposed as HA Scene entities (`scene.lifesmart_<slug>_<id_tail>`). Triggering calls `obj=doscene` SET. Only `cls in ("scene", "groupirc")` are surfaced this iteration; `groupsw` / `grouphw` / `grouprgbw` need light/switch semantics and are deferred.
- **`hub_info` cache** — `__init__.py` calls `cfg:getver` once at setup and stores the result in `entry_data["hub_info"]` so every hub-level entity reads from one cache instead of racing for its own request. Failure is non-fatal.
- **New platform files:** `button.py`, `scene.py`. `const.py` `PLATFORMS` extended accordingly.
- **Note:** the previous worry that `cfg:notify` expires after 300 s was a stale concern — `__init__.py` already re-sends the subscription every 90 s.

### 20260523r3 — 2026-05-23
- `manifest.json` metadata: `codeowners` → `["@raphael1688dev"]`; `documentation` and new `issue_tracker` point to <https://github.com/raphael1688dev/lifesmart_local_APP>.

### 20260523r2 — 2026-05-23
- **Per-device connectivity binary_sensor** added. Reads the `stat` common attribute (Local Interfaces §6.1) and exposes one `binary_sensor` (CONNECTIVITY, diagnostic) per device. Updates via both NOTIFY push (LI §4) and a 15-minute fallback poll.
- **`api.py` extension:** `_extract_state_changes` now also dispatches the device-level scalar `stat` field from `chg` items as virtual idx `"stat"`, so the existing `register_state_listener(me, idx, cb)` mechanism handles it.
- **New platform file:** `binary_sensor.py`; `const.py` `PLATFORMS` now includes `"binary_sensor"`.

### 20260523r1 — 2026-05-23
- **Per-device RF signal strength sensor** added. Reads the `lDbm` common attribute from `eps` / `ep` responses (Local Interfaces §6.1) and exposes one diagnostic `sensor` per device, in dBm, with `SensorDeviceClass.SIGNAL_STRENGTH`. Works for both battery and mains-powered devices (unlike the `rssi` command, which returns error 102 for battery devices).
- Sensors are placed in `EntityCategory.DIAGNOSTIC` so they don't clutter the main dashboard. Entity ID pattern: `sensor.<devtype>_<agt>_<me>_signal`.

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

Found a bug or want to contribute? Visit the GitHub repository:
<https://github.com/raphael1688dev/lifesmart_local_APP>

Issues: <https://github.com/raphael1688dev/lifesmart_local_APP/issues>

## License

This project is licensed under the MIT License.

## File Structure

<pre>
custom_components/lifesmart/
├── __init__.py
├── api.py
├── binary_sensor.py
├── button.py
├── config_flow.py
├── const.py
├── cover.py
├── manifest.json
├── remote.py
├── scene.py
├── sensor.py
├── services.yaml
├── switch.py
├── brand/
│   ├── icon.png
│   └── logo.png
└── translations/
    └── en.json
</pre>
