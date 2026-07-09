from database.query import ExecutableQuery


def delete_bot_account(account_id: int) -> ExecutableQuery:
    """Only drops the token record. Deleting the underlying `account` row cascades
    to this table, its permissions, and nulls out alias authorship."""
    return ExecutableQuery(
        "DELETE FROM bot_account WHERE account_id = $1",
        account_id,
    )
