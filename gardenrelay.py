#!/usr/bin/env python3
"""
garden_relay.py — BLE control for "ESP32 Garden" (single-byte bitmask characteristic)

Matches your ESP32 firmware:
  Service UUID:       7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0000
  Characteristic UUID:7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0001
  Payload format: 1 byte bitmask; bit0=Relay1, bit1=Relay2

Examples:
  # Read current bitmask
  python3 garden_relay.py --read

  # Set both relays explicitly: 0..3 (binary 00..11)
  python3 garden_relay.py --set-bits 3    # both ON
  python3 garden_relay.py --set-bits 0    # both OFF

  # Convenience flags for each relay (writes the composed mask)
  python3 garden_relay.py --r1 on --r2 off

  # Use a specific MAC instead of scanning by name
  python3 garden_relay.py --mac AA:BB:CC:DD:EE:FF --r1 off

Requirements:
  pip install bleak
"""

import argparse
import asyncio
from typing import Optional, List

from bleak import BleakClient, BleakScanner, BleakError

DEFAULT_NAME = "ESP32 Garden"
SVC_UUID  = "7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0000"
CHAR_UUID = "7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0001"


async def find_address_by_name(name: str, timeout: float) -> Optional[str]:
    print(f"[scan] Looking for '{name}' ({timeout}s)...")
    for d in await BleakScanner.discover(timeout=timeout):
        if d.name == name:
            print(f"[scan] Found {name}: {d.address}")
            return d.address
    print("[scan] Not found.")
    return None


async def read_bits(address: str, timeout: float) -> int:
    async with BleakClient(address, timeout=timeout) as client:
        if not await client.is_connected():
            raise BleakError("Failed to connect")
        data = await client.read_gatt_char(CHAR_UUID)
        if not data:
            raise BleakError("Empty read")
        bits = data[0] & 0x03
        print(f"[read] relayBits=0b{bits:02b} (0x{bits:02X})")
        return bits


async def write_bits(address: str, bits: int, timeout: float) -> None:
    bits &= 0x03
    async with BleakClient(address, timeout=timeout) as client:
        if not await client.is_connected():
            raise BleakError("Failed to connect")
        print(f"[write] -> 0b{bits:02b} (0x{bits:02X}) to {CHAR_UUID}")
        # ESP32 char supports WRITE/WWR; use WWR for speed
        await client.write_gatt_char(CHAR_UUID, bytes([bits]), response=False)
        print("[write] Done.")


def compose_bits(current: int, r1: Optional[str], r2: Optional[str], set_bits: Optional[int]) -> int:
    if set_bits is not None:
        return set_bits & 0x03
    bits = current & 0x03
    if r1 is not None:
        bits = (bits & ~0x01) | (0x01 if r1 == "on" else 0x00)
    if r2 is not None:
        bits = (bits & ~0x02) | (0x02 if r2 == "on" else 0x00)
    return bits & 0x03


async def main_async(args) -> int:
    address = args.mac
    if not address:
        address = await find_address_by_name(args.name, args.scan_timeout)
        if not address:
            return 1

    # Decide operation
    if args.read and args.set_bits is None and args.r1 is None and args.r2 is None:
        await read_bits(address, args.conn_timeout)
        return 0

    current = 0
    if args.read_first:
        try:
            current = await read_bits(address, args.conn_timeout)
        except Exception as e:
            print(f"[warn] read-first failed, assuming 0: {e}")
            current = 0

    target = compose_bits(current, args.r1, args.r2, args.set_bits)
    # Short-circuit if no change
    if args.read_first and target == current:
        print("[noop] Target equals current, nothing to write.")
        return 0

    # Retries
    last_err = None
    for attempt in range(1, args.retries + 1):
        try:
            await write_bits(address, target, args.conn_timeout)
            if args.read_back:
                await read_bits(address, args.conn_timeout)
            return 0
        except Exception as e:
            last_err = e
            print(f"[retry] {attempt}/{args.retries} failed: {e}")
            await asyncio.sleep(args.backoff)

    print(f"[error] Giving up after {args.retries} attempts: {last_err}")
    return 1


def build_parser() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Control ESP32 Garden relays via BLE (bitmask char).")
    tgt = p.add_mutually_exclusive_group()
    tgt.add_argument("--mac", help="Target MAC (AA:BB:CC:DD:EE:FF)")
    tgt.add_argument("--name", default=DEFAULT_NAME, help=f"Advertised Name (default '{DEFAULT_NAME}')")
    p.add_argument("--scan-timeout", type=float, default=6.0, help="Scan timeout seconds")
    p.add_argument("--conn-timeout", type=float, default=7.5, help="Connect timeout seconds")
    p.add_argument("--retries", type=int, default=3, help="Retry count")
    p.add_argument("--backoff", type=float, default=0.8, help="Seconds between retries")

    # Actions
    p.add_argument("--read", action="store_true", help="Read and print current relay bitmask")
    p.add_argument("--set-bits", type=int, choices=range(0,4), help="Explicit bitmask (0..3) to write")
    p.add_argument("--r1", choices=["on", "off"], help="Set Relay 1 state")
    p.add_argument("--r2", choices=["on", "off"], help="Set Relay 2 state")

    # Behaviour
    p.add_argument("--read-first", action="store_true", help="Read current, then only modify specified relays")
    p.add_argument("--read-back", action="store_true", help="Read after write to confirm")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        rc = asyncio.run(main_async(args))
    except KeyboardInterrupt:
        rc = 130
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
