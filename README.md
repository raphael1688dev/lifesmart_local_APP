# Local LifeSmart for Home Assistant

Control LifeSmart devices through your LifeSmart hub over the local network. The integration talks to the hub's local interface (OpenDev) over UDP. It needs no cloud account at runtime.

## Features

- Local control and real-time state push from the hub (NOTIFY events), with a slow fallback poll.
- Switches, curtain motors, IR remotes, temperature, battery, signal-strength and connectivity sensors.
- Button events from multi-control accessories and CUBE clickers.
- Hub-level firmware/OS/model/time-zone sensors, a reboot button, the hub's scenes, and its group scenes as switches and lights.
- Actions to set the hub's time zone, rename devices on the hub, upgrade the hub firmware, or factory-reset the hub.
- Devices paired to or removed from the hub show up in Home Assistant without a manual reload.
- Sub-devices are grouped under the hub device on the device page.
- UI setup, reconfiguration without removing the integration, diagnostics download, and Repairs notices.
- Translations: English, 繁體中文, 简体中文.

## Requirements

- Home Assistant **2026.11.0** or newer.
- A LifeSmart hub (Smart Station, NatureMini family, or DEFED) on the same LAN as Home Assistant.
- The hub's **local interface (OpenDev) enabled**, with the **model** and **token** LifeSmart assigned to you. See [Configuration](#configuration).
- UDP traffic allowed between Home Assistant and the hub. The hub listens on port 12348.
- Home Assistant's clock synced with NTP. Every request is signed with a timestamp.

## Installation

### HACS (recommended)

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/raphael1688dev/lifesmart_local_APP` with category **Integration**.
3. Install **Local LifeSmart** and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for **Local LifeSmart**.

### Manual

1. Copy `custom_components/lifesmart/` into your Home Assistant `custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration as in step 4 above.

## Configuration

The setup form asks for three values.

| Field | What to enter |
|---|---|
| IP Address | The hub's LAN address. A hostname also works. |
| OpenDev Model | The OpenDev **model** string LifeSmart assigned to you, for example `OD_XXX_XXX`. This is not the model printed on the hub. The form pre-fills `OD_ALI_TECH`; replace it if your assigned model is different. |
| Token | The OpenDev **token** that belongs to that model. The form accepts 16–64 letters and digits. |

The model and token are issued by LifeSmart as a pair and must be used together (Local Interfaces spec §3.2). Before the hub answers, the same pair has to be entered in the LifeSmart app: **Smart → + → Smart Template Management → Add Template → Common Templates → OpenDev**, then fill in name, model, token and encrypt key (spec §1.1).

**Changing settings later:** open the integration's menu and choose **Reconfigure** to change the IP, model or token. Home Assistant reloads the integration afterwards.

## Supported devices

### Sub-devices

| Platform | Device types | What you get |
|---|---|---|
| `switch` | `SL_SW_ND1/2/3` Stellar/Starry/Polar, `SL_SW_NS1/2/3` Moonstone, `SL_SW_IF1/2/3` and `SL_SW_RC` Traditional, `SL_NATURE` Nature Mini, `SL_MC_ND1/2/3` multi-control accessory | One switch per channel `L1`/`L2`/`L3` |
| `event` | `SL_MC_ND1/2/3` (buttons `B1`–`B3`), `SL_SC_BB` CUBE Clicker (button `B`) | Button events: press and release |
| `event` | `SL_SC_BB_V2` CUBE Clicker, new version (button `BN`) | Button events: single press, double press, press and hold |
| `cover` | `SL_P` MINS curtain motor controller | Open / close / stop |
| `remote` | `SL_P_IR` SPOT (mini), 922 RF version | One remote entity per SPOT, carrying every IR remote configured on it |
| `sensor` | `SL_NATURE` | Temperature from channel `T` (raw value ÷ 10 = °C) |
| `sensor` | `SL_SW_ND*`, `SL_MC_ND*`, `SL_SC_BB*` (channel `V`); `SL_P` (channel `P8`) | Battery, only when the device actually reports the channel |
| `sensor` | Every sub-device that reports `lDbm` | Signal strength in dBm (diagnostic) |
| `binary_sensor` | Every sub-device that reports `stat` | Connectivity (diagnostic) |

`SL_NATURE` temperature is not in the spec. The firmware sends it anyway, so it is supported.

### Hub

| Entity | Notes |
|---|---|
| `sensor.lifesmart_hub_firmware`, `sensor.lifesmart_hub_os`, `sensor.lifesmart_hub_model` | Read from `cfg:getver` at startup and once a day. |
| `sensor.lifesmart_hub_timezone` | The hub's time zone as `UTC+8`, with a `daylight_saving` attribute. Read at startup and once a day. |
| `button.lifesmart_hub_reboot` | Restarts the hub. Home Assistant asks for confirmation first. The integration reloads two minutes later. |
| `scene.lifesmart_<name>_<id>` | One scene per hub scene of type `scene` or `groupirc`. Activating it runs the scene on the hub. |
| `switch.lifesmart_<name>_<id>` | One switch per hub group scene of type `groupsw`. Turns the group on or off. |
| `light.lifesmart_<name>_<id>` | One light per hub group scene of type `grouphw` or `grouprgbw`. Turns the group on or off. |

### Entity IDs

Sub-device entity IDs follow `<platform>.<devtype>_<agt>_<me>_<channel>`, all lowercase. `agt` is the hub ID and `me` the device ID, so two hubs never collide. Remotes use `remote.<name>_<agt>_<me>`. Characters outside `a-z`, `0-9` and `_` become `_`.

## Sending IR commands

Use `remote.send_command` on the remote entity with one or more key names. The entity's `all_commands` attribute lists the available keys. When two IR remotes on the same SPOT share a key name, address one directly as `<remote_id>::<key>`; the IDs are in the `remotes` attribute.

```yaml
action: remote.send_command
target:
  entity_id: remote.living_room_spot_xxxx_2a01
data:
  command:
    - power
    - vol_up
```

The integration also offers `lifesmart.send_keys`, which takes a hub `remote_id` and one key or a list of keys. With several hubs the key goes to the hub that has that remote; pass `config_entry_id` to pick the hub yourself. The action fails if no hub is loaded or no hub accepts the key.

## Hub actions

Each action takes the hub's integration entry (`config_entry_id`), so several hubs stay apart.

| Action | What it does |
|---|---|
| `lifesmart.set_hub_timezone` | Sets the hub's time zone (`timezone`, whole hours from -12 to 12, east positive) and `daylight_saving`. |
| `lifesmart.rename_device` | Sets the name the hub stores for one of its devices (`device_id`), or for the hub itself when no device is given. The integration reloads afterwards so a renamed device shows its new name. A renamed hub looks the same in Home Assistant, because the hub device there is named after the integration entry; the new name shows in the LifeSmart app. |
| `lifesmart.upgrade_hub_firmware` | Downloads the latest official firmware from LifeSmart's server to the hub. It takes effect after the hub restarts; set `reboot` to restart as soon as the download finishes. |
| `lifesmart.factory_reset_hub` | Restores the hub's factory settings and restarts it. Requires `confirm: true`. This cannot be undone. |

## Troubleshooting

- **Failed to connect to the hub.** Check the IP, that Home Assistant and the hub share a LAN segment, that UDP is not blocked, and that the OpenDev template is enabled in the LifeSmart app.
- **Invalid token format.** The token must be 16–64 letters and digits, without spaces or symbols.
- **Clock difference too large (code 101).** The integration corrects small offsets itself. If the error persists, sync the Home Assistant host's clock with NTP.
- **No devices found on the hub.** The hub answered but reported no sub-devices. Check the model/token pair matches the one in the app's OpenDev template.
- **Integration shows "Retrying setup".** The hub did not answer at startup. Home Assistant retries on its own; check power and network.
- **Repairs: "LifeSmart hub is unreachable".** The hub has not answered for 5 minutes or more while Home Assistant was running. Check power and network. The notice disappears by itself once the hub answers again.
- **Repairs: "Cannot read hub firmware version".** The hub sensors keep the last values read, or stay empty if none were. Everything else keeps working. The integration tries again once a day.
- **A newly paired device does not appear.** The integration reloads about 10 seconds after the hub reports a paired or removed device. If the device still does not appear, reload the integration from its menu.
- **Reporting a bug.** Attach the diagnostics file from the integration's menu (**⋮ → Download diagnostics**). Token and signatures are redacted. For logs, add:

  ```yaml
  logger:
    logs:
      custom_components.lifesmart: debug
  ```

## Known limitations

- The curtain's position is read from channel `P1`. The spec does not say which channel reports curtain state, so this is not verified on hardware.
- Group scenes (`groupsw`, `grouphw`, `grouprgbw`) are on/off only. The hub does not report their state, so Home Assistant shows the last command it sent. Setting a group's colour is not supported: the spec does not say which parameter carries it.
- The scene trigger parameters follow the spec's example and have not been tested on every scene type.
- Scenes, group scenes, button events, and the rename, upgrade and factory-reset actions were written from the spec and have not been run against a real hub. `set_hub_timezone` has: it works on a Smart Station and a DEFED hub (firmware 1.0.94p10) from `20261110r1`. Up to `20261110r0` the request signature was built wrongly for scene triggers, for `set_hub_timezone`, and for `upgrade_hub_firmware` with `reboot`, so those very likely failed. The spec does not say how a scene trigger is signed; if one fails, please open an issue with the diagnostics file.
- The spec gives no example of the hub's "device paired" / "device removed" messages. The automatic reload follows the documented field names and has not been tested on hardware.
- IR remotes are supported only through `SL_P_IR` (SPOT mini).

## Upgrades that changed entity IDs

The integration renames affected entities in the registry automatically. Home Assistant does **not** rewrite automations, scripts or dashboards that refer to the old entity ID, so update those references yourself after these upgrades.

| Release | What changed | Who is affected |
|---|---|---|
| `20260523r6` | Remote IDs went from `remote.<name>_<me>` to `remote.<name>_<agt>_<me>` | Everyone with a remote |
| `20260803r0` | A `-` in an entity ID became `_` | Hubs whose ID (`agt`) contains `-` |
| `20260913r0` | Same fix for remote entity IDs | Hubs whose ID contains `-`, with a remote |
| `20260913r1` | Mixed-case legacy IDs are lowercased instead of mangled | Installs older than `20260523r6` upgrading directly |

**Coming from an old `lls` build:** remove the old integration entry first, add **Local LifeSmart**, then delete the orphaned `lls_*` entities.

## Changelog

Release notes for every version are on the [Releases page](https://github.com/raphael1688dev/lifesmart_local_APP/releases).

## Contributing

Issues and pull requests are welcome at <https://github.com/raphael1688dev/lifesmart_local_APP>.

Tests need only pytest; Home Assistant is stubbed. CI runs them on Python 3.14, which is what Home Assistant requires.

```bash
python3.14 -m venv .venv && .venv/bin/pip install pytest && .venv/bin/pytest tests/
```

## License

MIT
