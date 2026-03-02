from enum import StrEnum


class ErrorDetailCode(StrEnum):
    InternalServerError = "internal_server_error"
    BadRequestFields = "bad_request"
    NotFound = "not_found"

    InvalidTurnstile = "turnstile_invalid"
    InvalidUsername = "username_invalid"
    InvalidPassword = "password_invalid"
    InvalidDisplayName = "display_name_invalid"
    InvalidEmail = "email_invalid"
    UsernameConflict = "username_taken"
    EmailConflict = "email_taken"
    AccountNotFound = "account_not_found"
    EmailUnverified = "email_not_verified"
    EmailAlreadyVerified = "email_verified"

    InvalidAccountDetails = "invalid_login"

    NotLoggedIn = "not_logged_in"
    SessionExpired = "session_expired"
    SessionInvalid = "session_invalid"
    Banned = "banned"

    TooMuchData = "too_much_data"
    FileTooLarge = "file_too_large"
    InvalidImage = "invalid_image"
    Forbidden = "forbidden"
    Conflict = "conflict"

    PJSKMaintainence = "maintainence_pjsk"
    PJSKClientUnavailable = "pjsk_region_unavailable"


# openapi
ERROR_RESPONSE = {
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {"detail": {"type": "string", "example": "detail_code"}},
            }
        }
    }
}

COMMON_RESPONSES = {
    400: {
        "description": f"Invalid request data. (`{ErrorDetailCode.BadRequestFields}`)",
        **ERROR_RESPONSE,
    },
    401: {
        "description": f"Not logged in / token expired / invalid. (`{ErrorDetailCode.NotLoggedIn}`, `{ErrorDetailCode.SessionExpired}`, `{ErrorDetailCode.SessionInvalid}`)",
        **ERROR_RESPONSE,
    },
    403: {
        "description": f"Forbidden. (`{ErrorDetailCode.Banned}`, `{ErrorDetailCode.Forbidden}`)",
        **ERROR_RESPONSE,
    },
    503: {
        "description": f"PJSK requesting unavailable or in maintenance. (`{ErrorDetailCode.PJSKMaintainence}`, `{ErrorDetailCode.PJSKClientUnavailable}`)",
        **ERROR_RESPONSE,
    },
}
