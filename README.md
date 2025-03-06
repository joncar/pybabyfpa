# pybabyfpa

This package can be used to control Baby Brezza's Formula Pro Advanced WiFi.

NOTE: This is an unofficial community project which is not affiliated with Baby Brezza.

# Sample Usage

```python
import asyncio
from pybabyfpa import Fpa

async def main():
    fpa = Fpa()
    
    await fpa.login("email@example.com", "password")
    # await fpa.refresh(refresh_token_from_previous_session)

    # Basic user information
    print(f"Name: {fpa.first_name} {fpa.last_name}")
    print(f"Email: {fpa.email}")

    for device in fpa.devices:
        print(f"Device: {device.device_id} '{device.title}'")

    # Device information
    details = await fpa.get_device_details(fpa.devices[0].device_id)

    for bottle in details.bottles:
        print(f"Bottle {bottle.id}: '{bottle.title}' {bottle.volume}{bottle.volume_unit} of {bottle.formula}")

    # Start a bottle
    await fpa.start_bottle(details.bottles[0].id)

    await fpa.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```
