from typing import Literal
from pydantic import BaseModel, Field
import yaml


class ServerConfig(BaseModel):
    port: int
    environment: Literal["local", "production"]
    domain: str
    debug: bool


class PsqlConfig(BaseModel):
    host: str
    user: str
    database: str
    port: int
    password: str
    pool_min_size: int = Field(alias="pool-min-size")
    pool_max_size: int = Field(alias="pool-max-size")


class CloudflareTurnstileConfig(BaseModel):
    secret_key: str = Field(alias="secret-key")


class JWTConfig(BaseModel):
    secret: str


class S3Config(BaseModel):
    base_url: str = Field(alias="base-url")
    endpoint: str
    bucket_name: str = Field(alias="bucket-name")
    access_key_id: str = Field(alias="access-key-id")
    secret_access_key: str = Field(alias="secret-access-key")
    location: str


class Config(BaseModel):
    server: ServerConfig
    psql: PsqlConfig
    cloudflare_turnstile: CloudflareTurnstileConfig = Field(
        alias="cloudflare-turnstile"
    )
    jwt: JWTConfig
    s3: S3Config

    model_config = {"populate_by_name": True}


def get_config() -> Config:
    with open("config.yml", "r") as f:
        data = yaml.load(f, yaml.Loader)
    return Config.model_validate(data)
