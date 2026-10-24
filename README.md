# Local LifeSmart for Home Assistant

Control LifeSmart devices through your LifeSmart hub over the local network. The integration talks to the hub's local interface (OpenDev) over UDP. It needs no cloud account at runtime.

## Features

- Local control and real-time state push from the hub (NOTIFY events), with a slow fallback poll.
- Switches, curtain motors, IR remotes, temperature, battery, signal-strength and connectivity sensors.
- Hub-level firmware/OS/model sensors, a reboot button, and the hub's scenes.
- Sub-devices are grouped under the hub device on the device page.
- UI setup, reconfiguration without removing the integration, diagnostics download, and Repairs notices.
- Translations: English, 繁體中文, 简体中文.

## Requirements

- Home Assistant **2026.5.0** or newer.
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
| Hub Model | The OpenDev **model** string LifeSmart assigned to you, for example `OD_XXX_XXX`. This is not the model printed on the hub. The form pre-fills `OD_ALI_TECH`; replace it if your assigned model is different. |
| Token | The OpenDev **token** that belongs to that model. The form accepts 16–64 letters and digits. |

The model and token are issued by LifeSmart as a pair and must be used together (Local Interfaces spec §3.2). Before the hub answers, the same pair has to be entered in the LifeSmart app: **Smart → + → Smart Template Management → Add Template → Common Templates → OpenDev**, then fill in name, model, token and encrypt key (spec §1.1).

**Changing settings later:** open the integration's menu and choose **Reconfigure** to change the IP, model or token. Home Assistant reloads the integration afterwards.

## Supported devices

### Sub-devices

| Platform | Device types | What you get |
|---|---|---|
| `switch` | `SL_SW_ND1/2/3` Stellar/Starry/Polar, `SL_SW_NS1/2/3` Moonstone, `SL_SW_IF1/2/3` and `SL_SW_RC` Traditional, `SL_NATURE` Nature Mini | One switch per channel `L1`/`L2`/`L3` |
| `cover` | `SL_P` MINS curtain motor controller | Open / close / stop |
| `remote` | `SL_P_IR` SPOT (mini), 922 RF version | One remote entity per SPOT, carrying every IR remote configured on it |
| `sensor` | `SL_NATURE` | Temperature from channel `T` (raw value ÷ 10 = °C) |
| `sensor` | `SL_SW_ND*`, `SL_MC_ND*` (channel `V`); `SL_P` (channel `P8`) | Battery, only when the device actually reports the channel |
| `sensor` | Every sub-device that reports `lDbm` | Signal strength in dBm (diagnostic) |
| `binary_sensor` | Every sub-device that reports `stat` | Connectivity (diagnostic) |

`SL_NATURE` temperature is not in the spec. The firmware sends it anyway, so it is supported.

### Hub

| Entity | Notes |
|---|---|
| `sensor.lifesmart_hub_firmware`, `sensor.lifesmart_hub_os`, `sensor.lifesmart_hub_model` | Read once at startup from `cfg:getver`. Reload the integration after a hub firmware upgrade. |
| `button.lifesmart_hub_reboot` | Restarts the hub. Home Assistant asks for confirmation first. |
| `scene.lifesmart_<name>_<id>` | One scene per hub scene of type `scene` or `groupirc`. Activating it runs the scene on the hub. |

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

The integration also offers `lifesmart.send_keys`, which takes a hub `remote_id` and one key or a list of keys.

## Troubleshooting

- **Failed to connect to the hub.** Check the IP, that Home Assistant and the hub share a LAN segment, that UDP is not blocked, and that the OpenDev template is enabled in the LifeSmart app.
- **Invalid token format.** The token must be 16–64 letters and digits, without spaces or symbols.
- **Clock difference too large (code 101).** The integration corrects small offsets itself. If the error persists, sync the Home Assistant host's clock with NTP.
- **No devices found on the hub.** The hub answered but reported no sub-devices. Check the model/token pair matches the one in the app's OpenDev template.
- **Integration shows "Retrying setup".** The hub did not answer at startup. Home Assistant retries on its own; check power and network.
- **Repairs: "LifeSmart hub is unreachable".** The hub has not answered for 5 minutes or more while Home Assistant was running. Check power and network. The notice disappears by itself once the hub answers again.
- **Repairs: "Cannot read hub firmware version".** The three hub sensors stay empty. Everything else keeps working.
- **A newly paired device does not appear.** Reload the integration. New devices are only discovered at setup.
- **Reporting a bug.** Attach the diagnostics file from the integration's menu (**⋮ → Download diagnostics**). Token and signatures are redacted. For logs, add:

  ```yaml
  logger:
    logs:
      custom_components.lifesmart: debug
  ```

## Known limitations

- The curtain's position is read from channel `P1`. The spec does not say which channel reports curtain state, so this is not verified on hardware.
- Hub scenes of type `groupsw`, `grouphw` and `grouprgbw` are not exposed yet.
- The scene trigger parameters follow the spec's example and have not been tested on every scene type.
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
