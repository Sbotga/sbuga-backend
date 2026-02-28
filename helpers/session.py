import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, List
from dataclasses import dataclass, field
from fastapi import Header, HTTPException, status, Request, Depends
from core import SbugaFastAPI
from database import accounts
from database.models import Account, AccountPermission
from helpers.erroring import ErrorDetailCode


TOKEN_ALGORITHM = "HS256"
EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES = 60
ACCESS_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60
REFRESH_TOKEN_EXPIRE_MINUTES = 90 * 24 * 60
EXPIRES = {
    "access": ACCESS_TOKEN_EXPIRE_MINUTES,
    "refresh": REFRESH_TOKEN_EXPIRE_MINUTES,
    "email_verification": EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES,
}
SESSION_TYPES = Literal["access", "refresh", "email_verification"]


@dataclass
class SessionData:
    account_id: int
    type: SESSION_TYPES
    exp: datetime
    session_uuid: str
    extra: dict = field(default_factory={})


async def create_session(
    account_id: int,
    app: SbugaFastAPI,
    type: SESSION_TYPES = "access",
    extra: dict = {},
) -> str:
    async with app.acquire_db() as conn:
        account = await conn.fetchrow(accounts.get_account_by_id(account_id))

    payload = {
        "account_id": account_id,
        "type": type,
        "session_uuid": account.valid_session_uuid,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRES[type]),
        "extra": extra,
    }
    return jwt.encode(payload, _get_secret(app), algorithm=TOKEN_ALGORITHM)


def decode_session(token: str, app: SbugaFastAPI) -> SessionData:
    try:
        payload = jwt.decode(token, _get_secret(app), algorithms=[TOKEN_ALGORITHM])
        return SessionData(
            account_id=payload["account_id"],
            type=payload["type"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            session_uuid=payload["session_uuid"],
            extra=payload.get("extra", {}),
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
    return app.config.jwt.secret


def get_session(
    enforce_auth: bool = True,
    allow_banned_users: bool = False,
    enforce_type: Optional[SESSION_TYPES | List[SESSION_TYPES]] = "access",
    allow_unverified_email: bool = False,
):
    async def dependency(request: Request, authorization: Optional[str] = Header(None)):
        session = Session(
            enforce_auth=enforce_auth,
            allow_banned_users=allow_banned_users,
            enforce_type=enforce_type,
            allow_unverified_email=allow_unverified_email,
        )
        await session(request, authorization)
        return session

    return Depends(dependency)


class Session:
    def __init__(
        self,
        enforce_auth: bool = False,
        allow_banned_users: bool = True,
        enforce_type: Optional[SESSION_TYPES | List[SESSION_TYPES]] = None,
        allow_unverified_email: bool = False,
    ):
        self.enforce_auth = enforce_auth
        self.allow_banned_users = allow_banned_users
        self.enforce_type: Optional[list[SESSION_TYPES]] = (
            enforce_type if type(enforce_type) == list else [enforce_type]
        )
        self.allow_unverified_email = allow_unverified_email
        self._user_fetched: bool = False
        self._user: Account | None = None
        self._user_permissions: list[AccountPermission] | None = None
        self.permissions: list[str] = []

    async def user(self) -> Account:
        if not self._user_fetched:
            async with self.app.acquire_db() as conn:
                result = await conn.fetchrow(
                    accounts.get_account_by_id(self.session_data.account_id)
                )
                result_perms = await conn.fetch(
                    accounts.get_permissions(self.session_data.account_id)
                )

            if not result and self.enforce_auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ErrorDetailCode.NotLoggedIn.value,
                )

            # Validate session UUID
            if result and result.valid_session_uuid != self.session_data.session_uuid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ErrorDetailCode.SessionInvalid.value,
                )

            if (not result.email_verified) and (not self.allow_unverified_email):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ErrorDetailCode.EmailUnverified.value,
                )

            self._user = result
            self._user_fetched = True
            self._user_permissions = result_perms
            self.permissions = [p.permission for p in result_perms]

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

            if self.enforce_type and self.session_data.type not in self.enforce_type:
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
