from database.query import ExecutableQuery


def create_account(
    account_id: int, display_name: str, username: str, salted_password: str
) -> ExecutableQuery:
    return ExecutableQuery(
        """
        INSERT INTO account (id, display_name, username, salted_password)
        VALUES ($1, $2, $3, $4);
        """,
        account_id,
        display_name,
        username,
        salted_password,
    )
