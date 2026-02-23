from enum import StrEnum


class ErrorDetailCode(StrEnum):
    InternalServerError = "internal_server_error"
    BadRequestFields = "bad_request"

    InvalidTurnstile = "turnstile_invalid"
    InvalidUsername = "username_invalid"
    InvalidPassword = "password_invalid"
    InvalidDisplayName = "display_name_invalid"
    UsernameConflict = "username_taken"

    InvalidAccountDetails = "invalid_login"

    NotLoggedIn = "not_logged_in"
    SessionExpired = "session_expired"
    SessionInvalid = "session_invalid"
    Banned = "banned"

    TooMuchData = "too_much_data"
