from typing import TypedDict
import yaml

ConfigTypeServer = TypedDict(
    "ConfigTypeServer",
    {
        "port": int,
        "debug": bool,
    },
)
ConfigTypePsql = TypedDict(
    "ConfigTypePsql",
    {
        "host": str,
        "user": str,
        "database": str,
        "port": int,
        "password": str,
        "pool-min-size": int,
        "pool-max-size": int,
    },
)
ConfigTypeCloudflareTurnstile = TypedDict(
    "ConfigTypeCloudflareTurnstile",
    {"secret-key": str},
)

ConfigTypeJWT = TypedDict("ConfigTypeJWT", {"secret": str})

ConfigTypeS3 = TypedDict(
    "ConfigTypeS3",
    {
        "base-url": str,
        "endpoint": str,
        "bucket-name": str,
        "access-key-id": str,
        "secret-access-key": str,
        "location": str,
    },
)

ConfigType = TypedDict(
    "ConfigType",
    {
        "server": ConfigTypeServer,
        "psql": ConfigTypePsql,
        "cloudflare-turnstile": ConfigTypeCloudflareTurnstile,
        "jwt": ConfigTypeJWT,
        "s3": ConfigTypeS3,
    },
)


def get_config() -> ConfigType:
    with open("config.yml", "r") as f:
        config = yaml.load(
            f, yaml.Loader
        )  # NOTE: would be better to use pydantic-config
    return config
