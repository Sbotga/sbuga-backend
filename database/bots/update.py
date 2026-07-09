from database.query import ExecutableQuery


def set_bot_revoked(account_id: int, revoked: bool) -> ExecutableQuery:
    """Soft-disable a bot without deleting it (keeps alias authorship intact)."""
    return ExecutableQuery(
        "UPDATE bot_account SET revoked = $2 WHERE account_id = $1",
        account_id,
        revoked,
    )


def rotate_bot_token(account_id: int, token_hash: str) -> ExecutableQuery:
    return ExecutableQuery(
        "UPDATE bot_account SET token_hash = $2, revoked = FALSE WHERE account_id = $1",
        account_id,
        token_hash,
    )
