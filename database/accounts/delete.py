from database.query import ExecutableQuery


def delete_account(account_id: int) -> ExecutableQuery:
    return ExecutableQuery(
        """
        DELETE FROM account
        WHERE id = $1;
        """,
        account_id,
    )
