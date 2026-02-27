from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
from helpers.session import decode_session, create_session
import database as db

router = APIRouter()


class VerifyEmailBody(BaseModel):
    token: str


async def _verify_token(token: str, app: SbugaFastAPI) -> int:
    """Decode and validate email verification token, returns account_id."""
    session_data = decode_session(token, app)

    if session_data.type != "email_verification":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.SessionInvalid.value,
        )

    async with app.acquire_db() as conn:
        account = await conn.fetchrow(
            db.accounts.get_account_by_id(session_data.account_id)
        )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.SessionInvalid.value,
        )

    if account.email != session_data.extra.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.SessionInvalid.value,
        )

    if account.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.EmailAlreadyVerified.value,
        )

    async with app.acquire_db() as conn:
        await conn.execute(db.accounts.set_email_verified(account.id))
        await conn.execute(db.accounts.rotate_session_uuid(account.id))

    return account.id


@router.get(
    "/verify",
    summary="Verify email (browser)",
    description="Verifies email from a link clicked in the verification email. Redirects to the frontend on success.",
    responses={
        302: {"description": "Redirects to frontend."},
        401: {
            "description": f"Invalid or expired token. (`{ErrorDetailCode.SessionInvalid}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
async def verify_email_get(request: Request, token: str):
    app: SbugaFastAPI = request.app
    await _verify_token(token, app)
    return RedirectResponse(url=f"{app.config.server.frontend_domain}/email-verified")


@router.post(
    "/verify",
    summary="Verify email (frontend)",
    description="Verifies email from a token submitted by the frontend. Returns new access and refresh tokens.",
    responses={
        200: {
            "description": "Email verified successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "access_token": "eyJ...",
                        "refresh_token": "eyJ...",
                    }
                }
            },
        },
        400: {
            "description": f"Email already verified. (`{ErrorDetailCode.EmailAlreadyVerified}`)",
            **ERROR_RESPONSE,
        },
        401: {
            "description": f"Invalid or expired token. (`{ErrorDetailCode.SessionInvalid}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
async def verify_email_post(request: Request, body: VerifyEmailBody):
    app: SbugaFastAPI = request.app
    account_id = await _verify_token(body.token, app)

    access_token = await create_session(account_id, app, type="access")
    refresh_token = await create_session(account_id, app, type="refresh")

    return {
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
