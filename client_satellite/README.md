# Jarvis Satellite Clients

This folder contains the lightweight client software meant to run on distributed satellite nodes. A satellite node is a remote microphone/speaker unit that streams audio to the central Jarvis Server.

## Architectures Supported

### 1. `microcontrollers/` (ESP32, ESP32-S3, Arduino)
Designed for extreme low-cost setups (~10€).
- Requires an I2S Microphone (e.g., INMP441).
- Requires an I2S Amplifier/Speaker (e.g., MAX98357A).
- Uses **PlatformIO** and Arduino/ESP-IDF framework.
- Automatically provisioned and flashed via USB by the Jarvis Server, then updated Over-The-Air (OTA) via Wi-Fi.

### 2. `linux_edge/` (Raspberry Pi, Orange Pi, Generic Linux)
Designed for slightly more powerful setups where you might already have a Raspberry Pi running in another room.
- Can use standard USB microphones and 3.5mm/HDMI audio output.
- Runs a lightweight Python client (`satellite.py`).
- Jarvis Server can provision this automatically over SSH.

## Auto-Provisioning
You do not need to manually edit code to set Wi-Fi credentials or the Server IP. The `satellite_manager` in the Jarvis Core handles dynamic compilation and flashing automatically.
