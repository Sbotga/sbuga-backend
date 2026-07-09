from datetime import datetime

from pydantic import BaseModel

from typing import Optional


class Account(BaseModel):
    id: int
    display_name: str
    username: str
    description: str
    salted_password: str
    created_at: datetime
    updated_at: datetime
    banned: bool
    valid_session_uuid: str
    email: str
    base_email: str
    email_verified: bool

    profile_hash: Optional[str]
    banner_hash: Optional[str]


class AccountPermission(BaseModel):
    id: int
    account_id: int
    permission: str
    created_at: datetime


class BotAccount(BaseModel):
    """Token record for a bot. The bot itself is a normal `account` row, so its
    permissions live in `account_permissions` exactly like a human account's."""

    account_id: int
    name: str
    token_hash: str
    created_at: datetime
    revoked: bool


class SongAlias(BaseModel):
    id: int
    alias: str
    music_id: int
    region: str | None
    created_at: datetime
    created_by: int | None


class EventAlias(BaseModel):
    id: int
    alias: str
    event_id: int
    region: str | None
    created_at: datetime
    created_by: int | None
