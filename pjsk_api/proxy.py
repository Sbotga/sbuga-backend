from __future__ import annotations

import random
import threading
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import aiohttp
import yaml
from pydantic import BaseModel, Field

_PROXY_FILE = "proxy.yml"


class ProxyEntry(BaseModel):
    enabled: bool = True
    url: str
    username: Optional[str] = None
    password: Optional[str] = None

    def target(self) -> str:
        raw = self.url if "://" in self.url else f"http://{self.url}"
        if not self.username:
            return raw
        scheme, rest = raw.split("://", 1)
        auth = (
            self.username if not self.password else f"{self.username}:{self.password}"
        )
        return f"{scheme}://{auth}@{rest}"


class ProxyConfig(BaseModel):
    enabled: bool = False
    proxies: list[ProxyEntry] = Field(default_factory=list)


class ProxyPool:
    def __init__(self, config: ProxyConfig) -> None:
        self._active = config.enabled
        self._urls = [p.target() for p in config.proxies if p.enabled]
        random.shuffle(self._urls)
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self._active and bool(self._urls)

    @property
    def size(self) -> int:
        return len(self._urls)

    def rotate(self, blocked: Optional[str] = None) -> Optional[str]:
        """Pick a random proxy, avoiding `blocked` (the one that just failed)."""
        if not self.active:
            return None
        with self._lock:
            pool = [u for u in self._urls if u != blocked] or self._urls
            return random.choice(pool)


def load_proxy_config() -> ProxyConfig:
    path = Path(_PROXY_FILE)
    if not path.exists():
        return ProxyConfig()
    data = yaml.load(path.read_text("utf8"), yaml.Loader) or {}
    return ProxyConfig.model_validate(data)


_pool: Optional[ProxyPool] = None
_pool_lock = threading.Lock()


def get_pool() -> ProxyPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ProxyPool(load_proxy_config())
        return _pool


def aiohttp_proxy_kwargs(target: Optional[str]) -> dict:
    """Kwargs to spread into an aiohttp request. aiohttp needs credentials passed
    separately as proxy_auth, so split them out of the inline-auth target url."""
    if not target:
        return {}
    parsed = urlsplit(target)
    host = parsed.hostname or ""
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    proxy = f"{parsed.scheme}://{netloc}"
    if parsed.username:
        return {
            "proxy": proxy,
            "proxy_auth": aiohttp.BasicAuth(parsed.username, parsed.password or ""),
        }
    return {"proxy": proxy}


def requests_proxies(target: Optional[str]) -> Optional[dict]:
    """`proxies=` mapping for the `requests` library (inline auth is supported there)."""
    if not target:
        return None
    return {"http": target, "https": target}
