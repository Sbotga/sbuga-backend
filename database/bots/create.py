from database.query import ExecutableQuery


def create_bot_account(account_id: int, name: str, token_hash: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        INSERT INTO bot_account (account_id, name, token_hash)
        VALUES ($1, $2, $3);
        """,
        account_id,
        name,
        token_hash,
    )
