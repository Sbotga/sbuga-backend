from datetime import datetime

from pydantic import BaseModel


class Account(BaseModel):
    id: int
    display_name: str
    username: str
    salted_password: str
    created_at: datetime
    updated_at: datetime
    banned: bool
