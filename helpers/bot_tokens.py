"""Bot API tokens.

Tokens are high-entropy secrets, so they're stored as a plain SHA-256 digest rather
than a password hash: verification happens on every request and must be a single
indexed lookup (bcrypt/argon would be far too slow, and the entropy makes their
salting pointless here). The plaintext is shown once at creation and never stored.
"""

from __future__ import annotations

import hashlib
import secrets

BOT_TOKEN_PREFIX = "sbuga_bot_"
BOT_AUTH_SCHEME = "Bot"


def generate_bot_token() -> str:
    return f"{BOT_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_bot_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
