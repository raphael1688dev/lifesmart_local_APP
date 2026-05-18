# LifeSmart Local Integration for Home Assistant

Control your LifeSmart devices locally through Home Assistant without cloud dependency.

## Features
- Local control of LifeSmart devices
- Real-time state synchronization
- Support for switches, lights, and sensors
- No cloud connection required
- Fast response times

## Installation

1. Copy the `local_lifesmart` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to Configuration > Integrations
4. Click the + button and search for "LifeSmart Local"

## Configuration

You'll need:
- Hub IP address
- Model number (found on hub)
- Token (found in LifeSmart app)

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

## Usage

After setup, your devices will automatically appear in Home Assistant. The integration maintains perfect synchronization between:
- Home Assistant controls
- Physical switch changes
- LifeSmart mobile app controls

## Troubleshooting

Common fixes:
1. Ensure hub is on the same network
2. Check hub IP address is correct
3. Verify token is entered correctly
4. Confirm hub model number matches

## Contributing

Found a bug or want to contribute? Visit our GitHub repository.

## License

This project is licensed under the MIT License.

## File Structure

<pre>
custom_components/local_lifesmart/
├── __init__.py
├── api.py
├── const.py
├── manifest.json
├── config_flow.py
├── switch.py
└── README.md
</pre>

