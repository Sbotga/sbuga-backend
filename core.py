import asyncio
from fastapi import FastAPI, Request
from fastapi import status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from helpers.config_loader import Config
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
from helpers.converter_maps import rebuild_maps

_error_detail_values = {e.value for e in ErrorDetailCode}
_clients_ready = 0
_clients_ready_lock = asyncio.Lock()


def _extract_detail(exc_detail) -> tuple[str, dict | None]:
    """Returns (detail_code, cached_data | None)"""
    if isinstance(exc_detail, dict):
        return exc_detail.get(
            "detail", ErrorDetailCode.InternalServerError.value
        ), exc_detail.get("cached_data")
    return exc_detail, None


class SbugaFastAPI(FastAPI):
    def __init__(self, config: Config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config: Config = config
        self.debug: bool = config.server.debug

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

    @property
    def base_url(self) -> str:
        scheme = "http://" if self.config.server.environment == "local" else "https://"
        domain = (
            f"127.0.0.1:{self.config.server.port}"
            if self.config.server.environment == "local"
            else self.config.server.domain
        )
        return scheme + domain

    async def init(self) -> None:
        """Initialize all resources after worker process starts."""
        self.s3_session = aioboto3.Session(
            aws_access_key_id=self.config.s3.access_key_id,
            aws_secret_access_key=self.config.s3.secret_access_key,
            region_name=self.config.s3.location,
        )
        self.s3_session_getter = lambda: self.s3_session.resource(
            service_name="s3",
            endpoint_url=self.config.s3.endpoint,
        )
        self.s3_bucket = self.config.s3.bucket_name
        self.s3_asset_base_url = self.config.s3.base_url

        psql_config = self.config.psql
        self.db = await asyncpg.create_pool(
            host=psql_config.host,
            user=psql_config.user,
            database=psql_config.database,
            password=psql_config.password,
            port=psql_config.port,
            min_size=psql_config.pool_min_size,
            max_size=psql_config.pool_max_size,
            ssl="disable",  # XXX: todo, lazy for now
        )

        asyncio.create_task(self._set_en_pjsk_client())
        asyncio.create_task(self._set_jp_pjsk_client())

    async def _client_ready(self):
        global _clients_ready
        async with _clients_ready_lock:
            _clients_ready += 1
            if _clients_ready == 2:
                asyncio.create_task(
                    rebuild_maps(self.pjsk_clients["jp"], self.pjsk_clients["en"], self)
                )

    async def _set_en_pjsk_client(self):
        data = await get_en()
        client = PJSKClient(
            self, "en", app_version=data["app_version"], app_hash=data["app_hash"]
        )
        await client.start()
        await authenticate_client(client)
        await ensure_updated_masterdata(client)
        await ensure_updated_assetinfo(client)
        asyncio.create_task(download_and_process_assets(client))
        await set_client("en", client)
        await self._client_ready()

    async def _set_jp_pjsk_client(self):
        data = await get_jp()
        client = PJSKClient(
            self, "jp", app_version=data["app_version"], app_hash=data["app_hash"]
        )
        await client.start()
        await authenticate_client(client)
        await ensure_updated_masterdata(client)
        await ensure_updated_assetinfo(client)
        asyncio.create_task(download_and_process_assets(client))
        await set_client("jp", client)
        await self._client_ready()

    async def pjsk_request(
        self, region: str, request: RequestData[T], cached_data: Optional[dict] = None
    ) -> Optional[T]:
        return await request_with_retry(
            self.pjsk_clients[region], request, cached_data=cached_data, app=self
        )

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
        detail, cached_data = _extract_detail(exc.detail)

        if exc.status_code < 500:
            if exc.status_code == 404 and detail == "Not Found":
                detail = ErrorDetailCode.NotFound.value
            content = {"detail": detail}
            if cached_data is not None:
                content["cached_data"] = cached_data
            return JSONResponse(content=content, status_code=exc.status_code)
        else:
            if self.debug:
                raise exc
            content = {
                "detail": (
                    detail
                    if detail in _error_detail_values
                    else ErrorDetailCode.InternalServerError.value
                )
            }
            if cached_data is not None:
                content["cached_data"] = cached_data
            return JSONResponse(content=content, status_code=exc.status_code)

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
