#!/usr/bin/env python3
import logging
import argparse
import asyncio
import getpass
from pyfpa import Fpa


async def cmd_none(fpa, args):
    print("Nothing to do. See -h.")

async def cmd_me(fpa, args):
    if not fpa.has_me:
        await fpa.get_me()

    print(f"Name: {fpa.first_name} {fpa.last_name}")
    print(f"Email: {fpa.email}")

    for device in fpa.devices:
        print(f"Device: {device.id} / {device.device_id}: '{device.title}' Wifi:{device.wifi_mac_address} BLE:{device.ble_mac_address}")

async def cmd_login(fpa, args):
    password = getpass.getpass()
    await fpa.login(args.email, password)

    print(f"Refresh Token: {fpa.refresh_token}")
    print(f"Token: {fpa.token}")

    await cmd_me(fpa, args)

async def cmd_device(fpa, args):
    details = await fpa.get_device_details(args.device_id)

    for bottle in details.bottles:
        print(f"Bottle {bottle.id}: '{bottle.title}' {bottle.volume}{bottle.volume_unit} of {bottle.formula}")

async def cmd_start(fpa, args):
    await fpa.start_bottle(args.bottle_id)
    print("Attempted to start bottle")

# Main

async def main():
    parser = argparse.ArgumentParser("Control a Formula Pro Advanced Wifi.")
    parser.set_defaults(func=cmd_none)
    parser.add_argument(
        "-v",
        "--verbose",
        help="Show debug logging",
        action="store_const",
        const=logging.INFO,
        default=logging.WARN,
    )
    parser.add_argument("--refreshtoken", help="Refresh token", default=None)
    subparsers = parser.add_subparsers()

    parser_login = subparsers.add_parser("login", help="Login to get tokens")
    parser_login.add_argument("email", type=str)
    parser_login.set_defaults(func=cmd_login)

    parser_login = subparsers.add_parser("device", help="Get device details")
    parser_login.add_argument("device_id", type=str)
    parser_login.set_defaults(func=cmd_device)

    parser_login = subparsers.add_parser("start", help="Start a bottle")
    parser_login.add_argument("bottle_id", type=int)
    parser_login.set_defaults(func=cmd_start)

    args = parser.parse_args()

    logging.basicConfig(level=args.verbose)

    fpa = Fpa()

    if args.refreshtoken is not None:
        await fpa.refresh(args.refreshtoken)

    await args.func(fpa, args)

    await fpa.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())