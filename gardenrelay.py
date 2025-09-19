#!/usr/bin/env python3
"""
gardenrelay.py — Minimal BLE control for your ESP32 Garden

Firmware expects a single-byte bitmask on:
  Service UUID:       7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0000
  Characteristic UUID:7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0001

bit0 = Relay1, bit1 = Relay2

Usage examples:
  python3 gardenrelay.py r1 on
  python3 gardenrelay.py r2 off
  python3 gardenrelay.py both on
  python3 gardenrelay.py both off
"""

import sys, asyncio
from bleak import BleakClient, BleakScanner

DEVICE_NAME = "ESP32 Garden"
CHAR_UUID   = "7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0001"

async def set_relay(target_relay: str, state: str):
    # Find device by advertised name
    devices = await BleakScanner.discover(timeout=5.0)
    dev = next((d for d in devices if d.name == DEVICE_NAME), None)
    if not dev:
        print(f"Device '{DEVICE_NAME}' not found")
        return

    # Build bitmask
    if target_relay == "r1":
        bits = 0x01 if state == "on" else 0x00
    elif target_relay == "r2":
        bits = 0x02 if state == "on" else 0x00
    elif target_relay == "both":
        bits = 0x03 if state == "on" else 0x00
    else:
        print("Relay must be r1, r2, or both")
        return

    # Connect, write, disconnect
    async with BleakClient(dev.address) as client:
        await client.write_gatt_char(CHAR_UUID, bytes([bits]), response=False)
        print(f"Set {target_relay.upper()} {state.upper()}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: gardenrelay.py r1|r2|both on|off")
        sys.exit(1)
    asyncio.run(set_relay(sys.argv[1].lower(), sys.argv[2].lower()))
