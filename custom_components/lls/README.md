# LifeSmart Local Integration for Home Assistant

Control your LifeSmart devices locally through Home Assistant without cloud dependency.

## Features
- Local control of LifeSmart devices
- UDP local API support (OpenDev)
- Push state updates for supported entities
- Support for switches, sensors, covers, and IR remotes
- No cloud connection required
- Fast response times

## Installation

1. Copy this folder to `custom_components/lifesmart`
2. Restart Home Assistant
3. Go to Configuration > Integrations
4. Click the + button and search for "LifeSmart Local"

## Configuration

You'll need:
- Hub IP address
- Model number (provided by LifeSmart for OpenDev)
- Token (24 characters, provided by LifeSmart for OpenDev)

The integration communicates over UDP. By default it binds to local UDP port 12346 to receive hub replies and push updates.

## Supported Devices

Currently supports:
- SL_SW_NS1 (Single Switch)
- SL_SW_NS2 (Double Switch)
- SL_SW_NS3 (Triple Switch)
- SL_NATURE (Nature Series)
- SL_SW_IF1
- SL_SW_IF2
- SL_SW_IF3
- SL_SW_RC
- SL_P (Curtain module, basic open/close/stop)
- SL_P_IR (IR module as Home Assistant Remote)

## Usage

After setup, your devices will automatically appear in Home Assistant. The integration maintains perfect synchronization between:
- Home Assistant controls
- Physical switch changes
- LifeSmart mobile app controls

### Services

- lifesmart.send_keys
  - remote_id: Remote ID returned by the hub
  - keys: One key or a list of keys to send

## Troubleshooting

Common fixes:
1. Ensure hub is on the same network
2. Check hub IP address is correct
3. Verify token is entered correctly
4. Confirm hub model number matches
5. Ensure UDP port 12346 is available and not blocked by firewall

## Contributing

Found a bug or want to contribute? Visit our GitHub repository.

## License

This project is licensed under the MIT License.

## Testing

Run tests and syntax checks:

```bash
python -m unittest discover -s custom_components/lifesmart/tests -p "test_*.py"
```

