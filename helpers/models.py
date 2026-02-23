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

    profile_hash: Optional[str]
    banner_hash: Optional[str]
