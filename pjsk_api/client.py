import aiohttp
from msgpack import unpackb, packb
from pjsk_api.crypto import encrypt, decrypt
from pjsk_api.constants import keys
from typing import Any, Optional, Type
from pydantic import BaseModel


APP_PLATFORM_NAMES = {
    "ios": "iOS",
    "android": "Android",
}


class RequestData(BaseModel):
    base_url: str
    path: str
    method: str = "GET"
    data: Optional[dict] = None
    headers: Optional[dict] = None
    params: Optional[dict] = None
    response_model: Optional[Type[BaseModel]] = None

    model_config = {"arbitrary_types_allowed": True}


class PJSKClient:
    def __init__(
        self,
        region: str,
        app_version: str,
        app_hash: str,
        app_platform: str = "android",
        unity_version: str = "2022.3.21f1",
    ):
        self.region = region
        self.app_version = app_version
        self.app_hash = app_hash
        self.app_platform = app_platform
        self.unity_version = unity_version
        self._session: aiohttp.ClientSession = None

    @property
    def keyset(self):
        return keys[self.region]

    @property
    def default_headers(self) -> dict:
        platform = APP_PLATFORM_NAMES.get(self.app_platform, self.app_platform)
        return {
            "Accept": "application/octet-stream",
            "Content-Type": "application/octet-stream",
            "Accept-Encoding": "deflate, gzip",
            "User-Agent": f"UnityPlayer/{self.unity_version}",
            "X-Platform": platform,
            "X-DeviceModel": "sbuga/1.0",
            "X-OperatingSystem": platform,
            "X-Unity-Version": self.unity_version,
            "X-App-Version": self.app_version,
            "X-App-Hash": self.app_hash,
        }

    async def start(self):
        self._session = aiohttp.ClientSession(
            headers=self.default_headers,
            connector=aiohttp.TCPConnector(limit=100),
        )

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def _pack(self, data: dict) -> bytes:
        packed = packb(data, use_single_float=True)
        return encrypt(packed, self.keyset)

    def _unpack(self, data: bytes) -> Any:
        try:
            decrypted = decrypt(data, self.keyset)
            return unpackb(decrypted, raw=False)
        except Exception:
            return data

    async def request(self, req: RequestData) -> Any:
        url = f"{req.base_url.rstrip('/')}/{req.path.lstrip('/')}"
        body = self._pack(req.data) if req.data is not None else None

        async with self._session.request(
            method=req.method.upper(),
            url=url,
            data=body,
            params=req.params,
            headers=req.headers,
        ) as response:
            raw = await response.read()
            if response.status >= 400:
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=raw.decode(errors="replace"),
                )

            result = self._unpack(raw)

            if req.response_model is not None and isinstance(result, dict):
                return req.response_model.model_validate(result)

            return result

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.close()
