import asyncio
from fastapi import FastAPI, Request
from fastapi import status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from helpers.config_loader import ConfigType
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from database import DBConnWrapper

import asyncpg
import aioboto3

from typing import AsyncGenerator, Optional

from helpers.erroring import ErrorDetailCode

from pjsk_api import clients, PJSKClient, set_client
from pjsk_api.client import RequestData, T
from pjsk_api.requests.authenticate_client import authenticate_client
from pjsk_api.requests.ensure_updated_masterdata import ensure_updated_masterdata
from pjsk_api.requests.ensure_updated_assetinfo import ensure_updated_assetinfo
from pjsk_api.asset_handlers import download_and_process_assets
from pjsk_api.requests.request_handling import request_with_retry
from pjsk_api.app_ver_hash import get_en, get_jp


class SbugaFastAPI(FastAPI):
    def __init__(self, config: ConfigType, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config: ConfigType = config
        self.debug: bool = config["server"].get("debug", False)

        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=16)
        self.db: asyncpg.Pool | None = None

        self.s3_session: aioboto3.Session | None = None
        self.s3_session_getter: callable | None = None
        self.s3_bucket: str | None = None
        self.s3_asset_base_url: str | None = None

        self.pjsk_clients: dict[str, PJSKClient] = clients

        # Event handlers
        self.add_event_handler("shutdown", self.shutdown)

        # Exception handlers
        self.add_exception_handler(Exception, self.unhandled_exception_handler)
        self.add_exception_handler(
            RequestValidationError, self.validation_exception_handler
        )
        self.add_exception_handler(HTTPException, self.http_exception_handler)
        self.add_exception_handler(404, self.http_exception_handler)

    async def init(self) -> None:
        """Initialize all resources after worker process starts."""
        self.s3_session = aioboto3.Session(
            aws_access_key_id=self.config["s3"]["access-key-id"],
            aws_secret_access_key=self.config["s3"]["secret-access-key"],
            region_name=self.config["s3"]["location"],
        )
        self.s3_session_getter = lambda: self.s3_session.resource(
            service_name="s3",
            endpoint_url=self.config["s3"]["endpoint"],
        )
        self.s3_bucket = self.config["s3"]["bucket-name"]
        self.s3_asset_base_url = self.config["s3"]["base-url"]

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
        asyncio.create_task(self._set_jp_pjsk_client())

    async def _set_en_pjsk_client(self):
        data = await get_en()
        client = PJSKClient(
            "en", app_version=data["app_version"], app_hash=data["app_hash"]
        )
        await client.start()
        await authenticate_client(client)
        await ensure_updated_masterdata(client)
        await ensure_updated_assetinfo(client)
        asyncio.create_task(download_and_process_assets(client))
        await set_client("en", client)

    async def _set_jp_pjsk_client(self):
        data = await get_jp()
        client = PJSKClient(
            "jp", app_version=data["app_version"], app_hash=data["app_hash"]
        )
        await client.start()
        await authenticate_client(client)
        await ensure_updated_masterdata(client)
        await ensure_updated_assetinfo(client)
        asyncio.create_task(download_and_process_assets(client))
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
        if exc.status_code < 500:
            detail = exc.detail
            if exc.status_code == 404 and exc.detail == "Not Found":
                detail = ErrorDetailCode.NotFound.value
            return JSONResponse(content={"detail": detail}, status_code=exc.status_code)
        else:
            if self.debug:
                raise exc
            return JSONResponse(
                content={"detail": ErrorDetailCode.InternalServerError.value},
                status_code=exc.status_code,
            )

    async def validation_exception_handler(
        self, request: Request, exc: RequestValidationError
    ):
        if self.debug:
            raise exc
        return JSONResponse(
            content={"detail": ErrorDetailCode.BadRequestFields.value},
            status_code=400,
        )

    async def unhandled_exception_handler(self, request: Request, exc: Exception):
        if self.debug:
            raise exc
        return JSONResponse(
            content={"detail": ErrorDetailCode.InternalServerError.value},
            status_code=500,
        )

    async def shutdown(self):
        for client in self.pjsk_clients.values():
            if client:
                await client.close()

    def openapi(self):
        if self.openapi_schema:
            return self.openapi_schema
        schema = super().openapi()
        for path in schema.get("paths", {}).values():
            for operation in path.values():
                operation.get("responses", {}).pop("422", None)
        self.openapi_schema = schema
        return self.openapi_schema
