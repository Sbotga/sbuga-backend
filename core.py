import asyncio
from fastapi import FastAPI, Request
from fastapi import status, HTTPException
from fastapi.responses import JSONResponse
from helpers.config_loader import ConfigType
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from database import DBConnWrapper
import asyncpg

from typing import AsyncGenerator, Optional

from helpers.error_detail_codes import ErrorDetailCode

from pjsk_api import clients, PJSKClient, set_client
from pjsk_api.client import RequestData, T
from pjsk_api.requests.authenticate_client import authenticate_client
from pjsk_api.requests.ensure_updated_masterdata import ensure_updated_masterdata
from pjsk_api.requests.request_handling import request_with_retry
from pjsk_api.app_ver_hash import get_en, get_jp


class SbugaFastAPI(FastAPI):
    def __init__(self, config: ConfigType, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config: ConfigType = config
        self.debug: bool = config["server"].get("debug", False)

        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=16)
        self.db: asyncpg.Pool | None = None

        self.pjsk_clients: dict[str, PJSKClient] = clients

        self.exception_handlers.setdefault(HTTPException, self.http_exception_handler)

    async def init(self) -> None:
        """Initialize all resources after worker process starts."""
        psql_config = self.config["psql"]
        self.db = await asyncpg.create_pool(
            host=psql_config["host"],
            user=psql_config["user"],
            database=psql_config["database"],
            password=psql_config["password"],
            port=psql_config["port"],
            min_size=psql_config["pool-min-size"],
            max_size=psql_config["pool-max-size"],
            ssl="disable",  # XXX: todo, lazy for now
        )

        asyncio.create_task(self._set_en_pjsk_client())
        asyncio.create_task(self.set_jp_pjsk_client())

    async def _set_en_pjsk_client(self):
        data = await get_en()
        client = PJSKClient(
            "en", app_version=data["app_version"], app_hash=data["app_hash"]
        )
        await client.start()
        await authenticate_client(client)
        await ensure_updated_masterdata(client)
        await set_client("en", client)

    async def _set_jp_pjsk_client(self):
        data = await get_jp()
        client = PJSKClient(
            "jp", app_version=data["app_version"], app_hash=data["app_hash"]
        )
        await client.start()
        await authenticate_client(client)
        await ensure_updated_masterdata(client)
        await set_client("jp", client)

    async def pjsk_request(self, region: str, request: RequestData[T]) -> Optional[T]:
        return await request_with_retry(self.pjsk_clients[region], request, set_client)

    @asynccontextmanager
    async def acquire_db(self) -> AsyncGenerator[DBConnWrapper, None]:
        async with self.db.acquire() as conn:
            yield DBConnWrapper(conn)

    async def run_blocking(self, func, *args, **kwargs):
        if not self.executor:
            raise RuntimeError("Executor not initialized. Call init() first.")
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, lambda: func(*args, **kwargs)
        )

    async def http_exception_handler(self, request: Request, exc: HTTPException):
        if exc.status_code < 500 and exc.status_code != 422:
            return JSONResponse(
                content={"detail": exc.detail}, status_code=exc.status_code
            )
        elif exc.status_code == 422 and not self.debug:
            return JSONResponse(
                content={"detail": ErrorDetailCode.BadRequestFields.value},
                status_code=400,
            )
        else:
            if self.debug:
                raise exc
            return JSONResponse(
                content={"detail": ErrorDetailCode.InternalServerError.value},
                status_code=exc.status_code,
            )
