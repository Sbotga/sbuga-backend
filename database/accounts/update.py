from database.query import ExecutableQuery


def update_account_password(account_id: int, salted_password: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        UPDATE account
        SET salted_password = $2, updated_at = NOW()
        WHERE account_id = $1;
        """,
        account_id,
        salted_password,
    )


def update_account_username(account_id: int, username: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        UPDATE account
        SET username = $2, updated_at = NOW()
        WHERE account_id = $1;
        """,
        account_id,
        username,
    )


def update_account_display_name(account_id: int, display_name: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        UPDATE account
        SET display_name = $2, updated_at = NOW()
        WHERE account_id = $1;
        """,
        account_id,
        display_name,
    )
