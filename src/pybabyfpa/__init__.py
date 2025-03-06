from typing import List, Callable
import logging
import aiohttp
import asyncio
import urllib.parse

_LOGGER = logging.getLogger(__name__)

__version__ = '0.0.7'

class FpaError(Exception):
    code: int
    message: str

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

class FpaFormula:
    territory: str
    brand: str
    type: str
    stage: str
    setting: int
    model: str
    density: str

    def __init__(self, json):
        self.territory = json["territory"]
        self.brand = json["brand"]
        self.type = json["type"]
        self.stage = json["stage"]
        self.setting = json["setting"]
        self.model = json["model"]
        self.density = json["density"]

    def __str__(self):
        return f"{self.brand} {self.type}"

class FpaBottle:
    id: int
    title: str
    temperature: int
    powder: int
    volume: int
    volume_unit: str
    water_only: bool
    formula: FpaFormula | None

    def __init__(self, json):
        self.id = json["id"]
        self.title = json["title"]
        self.temperature = json["temperature"]
        self.powder = json["powder"]
        self.volume = json["volume"]
        self.volume_unit = json["volumeUnit"]
        self.water_only = json["waterOnly"]
        self.formula = FpaFormula(json["formula"]) if "formula" in json else None

class FpaBottleCreationLog:
    id: int
    volume: int
    volume_unit: str
    temperature: int
    bottle_id: int
    powder_setting: int
    water_only: bool
    completion_timestamp: str

    def __init__(self, json):
        self.id = json['id']
        self.volume = json['volume']
        self.volume_unit = json['volumeUnit']
        self.temperature = json['temperature']
        self.bottle_id = json['bottleId']
        self.powder_setting = json['powderSetting']
        self.water_only = json['waterOnly']
        self.completion_timestamp = json['completionTimestamp']

class FpaShadow:
    connected: bool

    # settings
    temperature: int
    powder: int
    volume: int
    volume_unit: str
    making_bottle: bool
    water_only: bool

    # hardware/alerts
    bottle_missing: bool
    funnel_cleaning_needed: bool
    funnel_out: bool
    lid_open: bool
    low_water: bool

    def __init__(self):
        self._data = {}

    def _merge(self, d1, d2):
        for k, v in d1.items():
            if k in d2:
                if isinstance(v, dict) and isinstance(d2[k], dict):
                    d2[k] = self._merge(v, d2[k])
        d1.update(d2)
        return d1

    def update(self, json):
        self._data = self._merge(self._data, json)
        _LOGGER.debug(f"Shadow Merged: {str(self._data)}")
        r = self._data['state']['reported']

        self.connected = r['connected']

        self.temperature = r['settings']["temperature"]
        self.powder = r['settings']["powder"]
        self.volume = r['settings']["volume"]
        self.volume_unit = r['settings']["volumeUnit"]
        self.making_bottle = r['settings']["makingBottle"]
        self.water_only = r['settings']["waterOnly"]

        alerts = r['hardware'].get('alerts', {})
        self.bottle_missing = alerts.get("bottleMissing", False)
        self.funnel_cleaning_needed = alerts.get("funnelCleaningNeeded", False)
        self.funnel_out = alerts.get("funnelOut", False)
        self.lid_open = alerts.get("lidOpen", False)
        self.low_water = alerts.get("lowWater", False)

class FpaDevice:
    id: str
    device_id: str
    title: str
    wifi_mac_address: str
    ble_mac_address: str

    has_details: bool

    bottles: List[FpaBottle]
    bottleCreationLog: List[FpaBottleCreationLog]
    shadow: FpaShadow

    connected: bool

    def __init__(self, json):
        self.id = json['id']
        self.device_id = json['deviceId']
        self.title = json['title']
        self.wifi_mac_address = json['wifiMacAddress']
        self.ble_mac_address = json['bleMacAddress']
        self.has_details = False
        self.connected = False

    def update_details(self, json):
        self.has_details = True
        self.bottles = [FpaBottle(b) for b in json["bottles"]]
        self.bottle_creation_log = [FpaBottleCreationLog(b) for b in json["bottleCreationLog"]]
        self.shadow = FpaShadow()
        self.shadow.update(json["shadow"])

class FpaDeviceClient:
    fpa: 'Fpa'
    device_id: str
    delay_seconds: int
    ping_seconds: int

    loop: asyncio.AbstractEventLoop
    _ws: aiohttp.ClientWebSocketResponse

    def __init__(self, fpa: 'Fpa', device_id: str):
        self.fpa = fpa
        self.device_id = device_id

        self.delay_seconds = 1
        self.ping_seconds = 600

        self._ws = None

        self.loop = asyncio.get_running_loop()
        self.loop.create_task(self._client())
        self.loop.create_task(self._ping())

    async def _ping(self):
        while not self.fpa.closed:
            if self._ws is not None:
                _LOGGER.info("Ping!")
                await self._ws.ping()
            await asyncio.sleep(self.ping_seconds)

    async def _client(self):
        while not self.fpa.closed:
            device = self.fpa._find_device(self.device_id)
            _LOGGER.info(f"Client for {device.device_id} connecting")
            async with self.fpa._session.ws_connect(f"{self.fpa.websockets_url}?Authorization={urllib.parse.quote_plus(self.fpa.token)}&deviceId={urllib.parse.quote_plus(self.device_id)}") as ws:
                self._ws = ws

                try:
                    device = self.fpa._find_device(self.device_id)
                    _LOGGER.info(f"Client for {device.device_id} connected")
                    device.connected = True
                    self.fpa._call_listeners(device)

                    self.delay_seconds = 1

                    while not ws.closed:
                        msg = await ws.receive_json()
                        if msg['subject'] == 'shadow-update':
                            device = self.fpa._find_device(msg['body']['deviceId'])
                            if not device.has_details:
                                await self.fpa.get_device_details(device.device_id)
                            device.shadow.update(msg['body'])
                            self.fpa._call_listeners(device)
                        else:
                            _LOGGER.info(f"Unknown subject '{msg['subject']}': {str(msg['body'])}")
                except Exception as exc:
                    _LOGGER.exception("Exception on WebSockets")
                finally:
                    self._ws = None

                    device = self.fpa._find_device(self.device_id)
                    _LOGGER.info(f"Client for {device.device_id} disconnected. "
                                 f"Delay {self.delay_seconds} seconds before reconnecting...")
                    device.connected = False
                    self.fpa._call_listeners(device)

            await asyncio.sleep(self.delay_seconds)
            self.delay_seconds = min(600, self.delay_seconds * 2)

            await self.fpa.refresh(self.fpa.refresh_token)

class Fpa:
    refresh_token: str
    token: str

    has_me: bool
    email: str
    first_name : str
    last_name: str
    devices: List[FpaDevice]

    api_url: str
    websockets_url: str
    _listeners: List[Callable[[FpaDevice], None]]
    _session: aiohttp.ClientSession
    closed: bool

    def __init__(self, session: aiohttp.ClientSession = None):
        self.has_me = False

        self.api_url = None
        self.websockets_url = None
        self._listeners = []
        self._session = session
        self.closed = False

        self._session_created = session is None
        if self._session_created:
            self._session = aiohttp.ClientSession()

    async def _initialize(self):
        if self.api_url is not None and self.websockets_url is not None:
            return

        async with self._session.get('https://info.babybrezzacloud.com') as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            self.api_url = f"https://{j['api']}"
            self.websockets_url = j['websockets']

    async def login(self, email: str, password: str):
        await self._initialize()
        jreq = {'email': email, 'password': password}
        async with self._session.post(f'{self.api_url}/authentication/login',
                                      json=jreq) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            self.refresh_token = j['refreshToken']
            self.token = j['token']
            self.email = j['email']
            self.first_name = j['firstName']
            self.last_name = j['lastName']
            self.devices = [FpaDevice(d) for d in j['devices']]
            self.has_me = True

    async def refresh(self, refresh_token: str):
        await self._initialize()
        jreq = {'refreshToken': refresh_token}
        async with self._session.post(f'{self.api_url}/authentication/refresh',
                                      json=jreq) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            self.refresh_token = j['refreshToken']
            self.token = j['token']
            if not self.has_me:
                await self.get_me()

    def _headers(self):
        return {
            'Authorization': self.token
        }

    async def get_me(self):
        async with self._session.get(f'{self.api_url}/authentication/me',
                                     headers=self._headers()) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            self.email = j['email']
            self.first_name = j['firstName']
            self.last_name = j['lastName']
            self.devices = [FpaDevice(d) for d in j['devices']]
            self.has_me = True

    def _find_device(self, device_id: str) -> FpaDevice:
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None

    async def get_device_details(self, device_id: str) -> FpaDevice:
        device = self._find_device(device_id)
        async with self._session.get(f'{self.api_url}/devices/{device_id}/details',
                                     headers=self._headers()) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            device.update_details(j)
            return device

    async def start_bottle(self, bottle_id: int):
        async with self._session.put(f'{self.api_url}/bottles/{bottle_id}/start',
                                     headers=self._headers()) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)

    def _call_listeners(self, device):
        loop = asyncio.get_running_loop()
        for listener in self._listeners:
            loop.call_soon(listener, device)

    async def connect_to_device(self, device_id: str):
        if not self.has_me:
            await self.get_me()
        device = self._find_device(device_id)
        if not device.has_details:
            await self.get_device_details(device_id)
        FpaDeviceClient(self, device_id)

    def add_listener(self, callback: Callable[[FpaDevice], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def remove():
            self._listeners.remove(callback)
        
        return remove

    async def close(self):
        if self._session_created:
            await self._session.close()
        self.closed = True
