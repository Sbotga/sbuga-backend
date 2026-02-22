import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
from dataclasses import dataclass
from fastapi import Header, HTTPException, status, Request, Depends
from core import SbugaFastAPI
from database import accounts
from helpers.models import Account
from helpers.error_detail_codes import ErrorDetailCode


TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_EXPIRE_DAYS = 90


@dataclass
class SessionData:
    account_id: int
    type: Literal["access", "refresh"]
    exp: datetime


def create_session(
    account_id: int, type: Literal["access", "refresh"] = "access"
) -> str:
    expire_days = (
        ACCESS_TOKEN_EXPIRE_DAYS if type == "access" else REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "account_id": account_id,
        "type": type,
        "exp": datetime.now(timezone.utc) + timedelta(days=expire_days),
    }
    return jwt.encode(payload, _get_secret(), algorithm=TOKEN_ALGORITHM)


def decode_session(token: str, app: SbugaFastAPI) -> SessionData:
    try:
        payload = jwt.decode(token, _get_secret(app), algorithms=[TOKEN_ALGORITHM])
        return SessionData(
            account_id=payload["account_id"],
            type=payload["type"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.SessionExpired.value,
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.SessionInvalid.value,
        )


def _get_secret(app: SbugaFastAPI) -> str:
    return app.config["jwt"]["secret"]


def get_session(
    enforce_auth: bool = True,
    allow_banned_users: bool = False,
    enforce_type: Optional[Literal["access", "refresh"]] = "access",
):
    async def dependency(request: Request, authorization: Optional[str] = Header(None)):
        session = Session(
            enforce_auth=enforce_auth,
            allow_banned_users=allow_banned_users,
            enforce_type=enforce_type,
        )
        await session(request, authorization)
        return session

    return Depends(dependency)


class Session:
    def __init__(
        self,
        enforce_auth: bool = False,
        allow_banned_users: bool = True,
        enforce_type: Optional[Literal["access", "refresh"]] = None,
    ):
        self.enforce_auth = enforce_auth
        self.allow_banned_users = allow_banned_users
        self.enforce_type = enforce_type
        self._user_fetched: bool = False
        self._user: Account = None

    async def user(self) -> Account:
        if not self._user_fetched:
            async with self.app.acquire_db() as conn:
                result = await conn.fetchrow(
                    accounts.get_account_by_id(self.session_data.account_id)
                )

            if not result and self.enforce_auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ErrorDetailCode.NotLoggedIn.value,
                )

            self._user = result
            self._user_fetched = True

        return self._user

    async def __call__(
        self, request: Request, authorization: Optional[str] = Header(None)
    ):
        self.app: SbugaFastAPI = request.app
        self.auth = authorization

        if not authorization and self.enforce_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorDetailCode.NotLoggedIn.value,
            )

        if authorization:
            self.session_data = decode_session(authorization, self.app)
            self.account_id = self.session_data.account_id

            if self.enforce_type and self.session_data.type != self.enforce_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ErrorDetailCode.SessionInvalid.value,
                )

            user = await self.user()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ErrorDetailCode.NotLoggedIn.value,
                )
            if not self.allow_banned_users and user.banned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ErrorDetailCode.Banned.value,
                )
        else:
            self.session_data = None
            self.account_id = None

        return self
