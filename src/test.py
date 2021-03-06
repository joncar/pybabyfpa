#!/usr/bin/env python3
import logging
import argparse
import asyncio
import getpass
import datetime
from pybabyfpa import Fpa, FpaDevice


async def cmd_none(fpa, args):
    print("Nothing to do. See -h.")

async def cmd_me(fpa, args):
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

async def cmd_listen(fpa, args):
    def device_updated(device: FpaDevice):
        print(f"{datetime.datetime.now()}: " +
              ('connected ' if device.connected else '') +
              ('bottle_missing ' if device.shadow.bottle_missing else '') +
              ('funnel_cleaning_needed ' if device.shadow.funnel_cleaning_needed else '') +
              ('funnel_out ' if device.shadow.funnel_out else '') +
              ('lid_open ' if device.shadow.lid_open else '') +
              ('low_water ' if device.shadow.low_water else '') +
              ('making_bottle ' if device.shadow.making_bottle else '') +
              ('shadow_connected ' if device.shadow.connected else '') +
              ('water_only ' if device.shadow.water_only else '') +
              f"{device.shadow.volume}{device.shadow.volume_unit}")

    remove = fpa.add_listener(device_updated)
    await fpa.connect_to_device(args.device_id)

    await asyncio.Event().wait()
    remove()

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

    parser_login = subparsers.add_parser("listen", help="Listen for events")
    parser_login.add_argument("device_id", type=str)
    parser_login.set_defaults(func=cmd_listen)

    args = parser.parse_args()

    logging.basicConfig(level=args.verbose, format='%(asctime)s %(message)s')

    fpa = Fpa()

    if args.refreshtoken is not None:
        await fpa.refresh(args.refreshtoken)

    await args.func(fpa, args)

    await fpa.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())