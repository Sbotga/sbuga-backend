from __future__ import annotations
import aiohttp
import json
import aiofiles
import asyncio
from msgpack import unpackb, packb
from pjsk_api.crypto import encrypt, decrypt
from pjsk_api.constants import keys
from typing import Any, Optional, Type, TypeVar, Generic, TYPE_CHECKING
from pydantic import BaseModel
from pathlib import Path
from .models import SekaiUserAuthData

if TYPE_CHECKING:
    from core import SbugaFastAPI

APP_PLATFORM_NAMES = {
    "ios": "iOS",
    "android": "Android",
}

MAX_USERS = 25
T = TypeVar("T", bound=BaseModel)


class RequestData(BaseModel, Generic[T]):
    base_url: str
    path: str
    method: str = "GET"
    data: Optional[dict] = None
    headers: Optional[dict] = None
    params: Optional[dict] = None
    response_model: Optional[Type[T]] = None

    trailing_slash: bool = (
        False  # because VERY rarely, some routes have a trailing slash (don't ask me lol)
    )

    model_config = {"arbitrary_types_allowed": True}


class UserSlot:
    def __init__(self):
        self.session: aiohttp.ClientSession = None
        self.user: SekaiUserAuthData | None = None
        self.user_id: int | None = None
        self.credential: str | None = None
        self.in_use: bool = False


class PJSKClient:
    def __init__(
        self,
        app: SbugaFastAPI,
        region: str,
        app_version: str,
        app_hash: str,
        app_platform: str = "android",
        unity_version: str = "2022.3.21f1",
        num_users: int = 5,
    ):
        self.app: SbugaFastAPI = app

        self.region = region
        self.app_version = app_version
        self.app_hash = app_hash
        self.app_platform = app_platform
        self.unity_version = unity_version
        self.num_users = min(max(1, num_users), MAX_USERS)

        self.is_authenticated: bool = False
        self.got_426: bool = False

        self.data_path: Path = Path("pjsk_api") / "data" / region
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.master_cache: dict[str, Any] = {}

        self._slots: list[UserSlot] = [UserSlot() for _ in range(self.num_users)]
        self._slot_semaphore: asyncio.Semaphore = asyncio.Semaphore(self.num_users)
        self._slot_lock: asyncio.Lock = asyncio.Lock()

        # shared headers applied to all slots
        self._shared_headers: dict[str, str] = {}

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

    def update_shared_headers(self, headers: dict[str, str]):
        """Update headers that are applied to ALL slots (e.g. X-Data-Version, X-Asset-Version)."""
        self._shared_headers.update(headers)
        for slot in self._slots:
            if slot.session:
                slot.session._default_headers.update(headers)

    async def start(self):
        for slot in self._slots:
            slot.session = aiohttp.ClientSession(
                headers={**self.default_headers, **self._shared_headers},
                connector=aiohttp.TCPConnector(limit=1),
            )

    async def close(self):
        for slot in self._slots:
            if slot.session:
                await slot.session.close()
                slot.session = None

    async def _acquire_slot(self) -> UserSlot:
        await self._slot_semaphore.acquire()
        async with self._slot_lock:
            for slot in self._slots:
                if not slot.in_use:
                    slot.in_use = True
                    return slot
        raise RuntimeError("No available slots despite semaphore.")

    def _release_slot(self, slot: UserSlot):
        slot.in_use = False
        self._slot_semaphore.release()

    def _pack(self, data: dict) -> bytes:
        packed = packb(data, use_single_float=True)
        return encrypt(packed, self.keyset)

    def _unpack(self, data: bytes) -> Any:
        try:
            decrypted = decrypt(data, self.keyset)
            return unpackb(decrypted, raw=False, strict_map_key=False)
        except Exception:
            return data

    async def get_master(self, file: str) -> Any:
        if file in self.master_cache:
            return self.master_cache[file]

        master_path = self.data_path / "master" / f"{file}.json"
        async with aiofiles.open(master_path, "r", encoding="utf8") as f:
            data = json.loads(await f.read())
        self.master_cache[file] = data
        return data

    async def _request_on_slot(
        self, slot: UserSlot, req: RequestData[T]
    ) -> Optional[T]:
        url = f"{req.base_url.rstrip('/')}/{req.path.lstrip('/')}".format_map(
            {"user_id": slot.user_id}
        )
        if req.trailing_slash:
            url = url.rstrip("/") + "/"
        else:
            url = url.rstrip("/")
        body = self._pack(req.data) if req.data is not None else None

        async with slot.session.request(
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
                err = aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=raw.decode(errors="replace"),
                )
                err.slot = slot
                raise err

            if "Set-Cookie" in response.headers:
                self.update_shared_headers({"Cookie": response.headers["Set-Cookie"]})

            session_token = response.headers.get("X-Session-Token")
            if session_token:
                slot.session._default_headers.update({"X-Session-Token": session_token})

            result = self._unpack(raw)

            if req.response_model is not None and isinstance(result, dict):
                return req.response_model.model_validate(result)

            return result

    async def request(self, req: RequestData[T]) -> Optional[T]:
        slot = await self._acquire_slot()
        try:
            return await self._request_on_slot(slot, req)
        finally:
            self._release_slot(slot)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.close()
