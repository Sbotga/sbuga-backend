from database.query import ExecutableQuery


def create_account(
    account_id: int, username: str, salted_password: str
) -> ExecutableQuery:
    return ExecutableQuery(
        """
        INSERT INTO account (account_id, username, salted_password)
        VALUES ($1, $2, $3);
        """,
        account_id,
        username,
        salted_password,
    )
