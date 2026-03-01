from fastapi import APIRouter, Request
from core import SbugaFastAPI
from helpers.session import get_session, create_session, Session
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE

router = APIRouter()


@router.post(
    "",
    summary="Refresh access token",
    description="Exchanges a refresh token for a new access token.",
    responses={
        200: {
            "description": "New access token.",
            "content": {"application/json": {"example": {"token": "eyJ..."}}},
        },
        401: {
            "description": (
                f"Not logged in, token expired, or wrong token type. "
                f"(`{ErrorDetailCode.NotLoggedIn}`, `{ErrorDetailCode.SessionExpired}`, `{ErrorDetailCode.SessionInvalid}`)"
            ),
            **ERROR_RESPONSE,
        },
        403: {
            "description": f"User banned. (`{ErrorDetailCode.Banned}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Auth"],
)
async def main(
    request: Request, session: Session = get_session(enforce_type="refresh")
):
    app: SbugaFastAPI = request.app
    access_token = await create_session(
        session.account_id,
        app,
        type=(
            "access" if (await session.user()).email_verified else "email_verification"
        ),
        extra=(
            {}
            if (await session.user()).email_verified
            else {"email": (await session.user()).email}
        ),
    )
    return {"token": access_token}
