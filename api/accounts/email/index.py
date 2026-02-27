from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
from helpers.session import get_session, Session, create_session
from helpers import emails

router = APIRouter()


@router.post(
    "/send",
    summary="Send verification email",
    description="Sends a verification email to the authenticated account's email address. Can be used to resend if not yet verified.",
    responses={
        200: {
            "description": "Verification email sent.",
            "content": {"application/json": {"example": {"success": True}}},
        },
        400: {
            "description": f"Email already verified. (`{ErrorDetailCode.EmailAlreadyVerified}`)",
            **ERROR_RESPONSE,
        },
        401: {
            "description": f"Not logged in. (`{ErrorDetailCode.NotLoggedIn}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
@router.post(
    "/resend",
    include_in_schema=False,
)
async def send_verification_email(
    request: Request,
    session: Session = get_session(
        enforce_auth=True,
        allow_unverified_email=True,
        enforce_type="email_verification",
    ),
):
    app: SbugaFastAPI = request.app
    user = await session.user()

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.EmailAlreadyVerified.value,
        )

    token = await create_session(
        user.id,
        app,
        type="email_verification",
        extra={"email": user.email},
    )

    await emails.send_verification_email(
        app=app,
        to_email=user.email,
        display_name=user.display_name,
        username=user.username,
        token=token,
    )

    return {"success": True}
