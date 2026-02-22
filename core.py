import asyncio
from fastapi import FastAPI, Request
from fastapi import status, HTTPException
from fastapi.responses import JSONResponse
from helpers.config_loader import ConfigType
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from database import DBConnWrapper
import asyncpg
from typing import AsyncGenerator

from authlib.integrations.starlette_client import OAuth

from helpers.error_detail_codes import ErrorDetailCode


class SbugaFastAPI(FastAPI):
    def __init__(self, config: ConfigType, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config: ConfigType = config
        self.debug: bool = config["server"].get("debug", False)

        self.executor: ThreadPoolExecutor | None = None
        self.auth: str | None = None
        self.auth_header: str | None = None
        self.token_secret_key: str | None = None
        self.db: asyncpg.Pool | None = None

        self.oauth: OAuth | None = None

        self.exception_handlers.setdefault(HTTPException, self.http_exception_handler)

    async def init(self) -> None:
        """Initialize all resources after worker process starts."""
        self.executor = ThreadPoolExecutor(max_workers=16)

        self.auth = self.config["server"]["auth"]
        self.auth_header = self.config["server"]["auth-header"]
        self.token_secret_key = self.config["server"]["token-secret-key"]

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

    @asynccontextmanager
    async def acquire_db(self) -> AsyncGenerator[DBConnWrapper]:
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
