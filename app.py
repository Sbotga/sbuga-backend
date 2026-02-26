import os, importlib, traceback
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, status
from starlette.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from helpers.erroring import ERROR_RESPONSE, ErrorDetailCode
from helpers.config_loader import get_config
from core import SbugaFastAPI

config = get_config()
debug = config.server.debug

if debug:
    app = SbugaFastAPI(
        config=config,
        responses={
            500: {
                "description": f"Internal server error. (`{ErrorDetailCode.InternalServerError}`)",
                **ERROR_RESPONSE,
            },
        },
    )
else:
    app = SbugaFastAPI(
        config=config,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        responses={
            500: {
                "description": f"Internal server error. (`{ErrorDetailCode.InternalServerError}`)",
                **ERROR_RESPONSE,
            },
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if config.server.environment == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[config.server.domain])


@app.middleware("http")
async def force_https_redirect(request, call_next):
    response = await call_next(request)

    if not debug:
        if response.headers.get("Location"):
            response.headers["Location"] = response.headers.get("Location").replace(
                "http://", "https://", 1
            )

    return response


def load_routes(folder, cleanup: bool = True):
    global app

    routes = []

    def traverse_directory(directory):
        for root, dirs, files in os.walk(directory, topdown=False):
            for file in files:
                if not "__pycache__" in root and file.endswith(".py"):
                    route_name: str = (
                        os.path.join(root, file)
                        .removesuffix(".py")
                        .replace("\\", "/")
                        .replace("/", ".")
                    )
                    if "{" in route_name and "}" in route_name:
                        routes.append((route_name, False))
                    else:
                        routes.append((route_name, True))

    traverse_directory(folder)

    routes.sort(key=lambda x: (not x[1], x[0]))

    for route_name, is_static in routes:
        try:
            route = importlib.import_module(route_name)
        except NotImplementedError:
            continue

        route_name_parts = route_name.split(".")

        if route_name.endswith(".index"):
            del route_name_parts[-1]

        route_name = ".".join(route_name_parts)
        app.include_router(
            route.router,
            prefix="/" + route_name.replace(".", "/"),
            tags=route.router.tags,
        )

        print(f"[API] Loaded Route {route_name}")

    if cleanup:
        for root, dirs, _ in os.walk(folder, topdown=False):
            if "__pycache__" in dirs:
                pycache_path = os.path.join(root, "__pycache__")
                import shutil

                shutil.rmtree(pycache_path, ignore_errors=True)
                print(f"[API] Removed __pycache__ at {pycache_path}")


async def startup_event():
    await app.init()
    folder = "api"
    if len(os.listdir(folder)) == 0:
        print("[WARN] No routes loaded.")
    else:
        load_routes(folder, cleanup=debug)
        print("Routes loaded!")


app.add_event_handler("startup", startup_event)


async def start_fastapi():
    uvicorn_config = uvicorn.Config(
        "app:app",
        host="0.0.0.0",
        port=config.server.port,
        workers=8,
        access_log=debug,
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()


if __name__ == "__main__":
    raise SystemExit("Please run main.py")
