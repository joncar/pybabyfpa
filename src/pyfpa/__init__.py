from typing import List
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

class FpaError(Exception):
    code: int
    message: str

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

class FpaDevice:
    id: str
    device_id: str
    title: str
    wifi_mac_address: str
    ble_mac_address: str

    def __init__(self, json):
        self.id = json['id']
        self.device_id = json['deviceId']
        self.title = json['title']
        self.wifi_mac_address = json['wifiMacAddress']
        self.ble_mac_address = json['bleMacAddress']

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
    formula: FpaFormula

    def __init__(self, json):
        self.id = json["id"]
        self.title = json["title"]
        self.temperature = json["temperature"]
        self.powder = json["powder"]
        self.volume = json["volume"]
        self.volume_unit = json["volumeUnit"]
        self.water_only = json["waterOnly"]
        self.formula = FpaFormula(json["formula"])

class FpaDeviceDetails:
    bottles: List[FpaBottle]

    def __init__(self, json):
        self.bottles = [FpaBottle(b) for b in json["bottles"]]

class Fpa:
    refresh_token: str
    token: str

    has_me: bool
    email: str
    first_name : str
    last_name: str
    devices: List[FpaDevice]

    def __init__(self, session: aiohttp.ClientSession = None):
        self._session = session

        self._session_created = session is None
        if self._session_created:
            self._session = aiohttp.ClientSession()

        self.has_me = False

    async def login(self, email, password):
        jreq = {'email': email, 'password': password}
        async with self._session.post('https://api.babybrezzacloud.com/authentication/login',
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

    async def refresh(self, refresh_token):
        jreq = {'refreshToken': refresh_token}
        async with self._session.post('https://api.babybrezzacloud.com/authentication/refresh',
                                      json=jreq) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            self.refresh_token = j['refreshToken']
            self.token = j['token']

    def _headers(self):
        return {
            'Authorization': self.token
        }

    async def get_me(self):
        async with self._session.get('https://api.babybrezzacloud.com/authentication/me',
                                     headers=self._headers()) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            self.email = j['email']
            self.first_name = j['firstName']
            self.last_name = j['lastName']
            self.devices = [FpaDevice(d) for d in j['devices']]
            self.has_me = True

    async def get_device_details(self, device_id):
        async with self._session.get(f'https://api.babybrezzacloud.com/devices/{device_id}/details',
                                     headers=self._headers()) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)
            return FpaDeviceDetails(j)

    async def start_bottle(self, bottle_id):
        async with self._session.put(f'https://api.babybrezzacloud.com/bottles/{bottle_id}/start',
                                     headers=self._headers()) as resp:
            j = await resp.json()
            if resp.status != 200:
                raise FpaError(resp.status, j.message)

    async def close(self):
        if self._session_created:
            await self._session.close()
