import aiohttp
import json
import aiofiles
from msgpack import unpackb, packb
from pjsk_api.crypto import encrypt, decrypt
from pjsk_api.constants import keys
from typing import Any, Optional, Type, TypeVar, Generic
from pydantic import BaseModel
from pathlib import Path
from .models import SekaiUserAuthData

APP_PLATFORM_NAMES = {
    "ios": "iOS",
    "android": "Android",
}

T = TypeVar("T", bound=BaseModel)


class RequestData(BaseModel, Generic[T]):
    base_url: str
    path: str
    method: str = "GET"
    data: Optional[dict] = None
    headers: Optional[dict] = None
    params: Optional[dict] = None
    response_model: Optional[Type[T]] = None

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

        self.is_authenticated: bool = False
        self.user: SekaiUserAuthData | None = None
        self.user_id: int | None = None

        self.data_path: Path = Path("pjsk_api") / "data" / region
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.master_cache: dict[str, dict] = {}

        self.got_426: bool = False

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

    async def get_master(self, file: str) -> dict:
        if file in self.master_cache:
            return self.master_cache[file]

        master_path = self.data_path / "master" / f"{file}.json"

        async with aiofiles.open(master_path, "r", encoding="utf8") as f:
            data = json.loads(await f.read())
        self.master_cache[file] = data
        return data

    async def request(self, req: RequestData[T]) -> Optional[T]:
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
                if response.status == 426:
                    self.got_426 = True
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=raw.decode(errors="replace"),
                )

            if "Set-Cookie" in response.headers:
                self._session.headers.update({"Cookie": response.headers["Set-Cookie"]})

            session_token = response.headers.get("X-Session-Token")
            if session_token:
                self._session.headers.update({"X-Session-Token": session_token})

            result = self._unpack(raw)

            if req.response_model is not None and isinstance(result, dict):
                return req.response_model.model_validate(result)

            return result

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.close()
