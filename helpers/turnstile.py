import uuid
from typing import Optional

import aiohttp

from core import SbugaFastAPI

# NOTE https://developers.cloudflare.com/turnstile/get-started/server-side-validation/


async def verify_turnstile(
    app: SbugaFastAPI,
    turnstile_response: str,
    ip: Optional[str] = None,
    retries: int = 3,
) -> bool:
    idempotency_key = str(uuid.uuid4())

    data = {
        "secret": app.config.cloudflare_turnstile.secret_key,
        "response": turnstile_response,
        "idempotency_key": idempotency_key,
    }

    if ip:
        data["remoteip"] = ip

    async with aiohttp.ClientSession() as session:
        for attempt in range(retries):
            try:
                async with session.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data=data,
                ) as resp:
                    result = await resp.json()
                    return result.get("success", False)
            except aiohttp.ClientError:
                if attempt == retries - 1:
                    raise

    return False
