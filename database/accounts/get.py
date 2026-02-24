from helpers.models import Account
from database.query import SelectQuery


def get_account_by_id(account_id: int) -> SelectQuery[Account]:
    return SelectQuery(
        Account,
        """
        SELECT * FROM account WHERE id = $1;
        """,
        account_id,
    )


def get_account_by_username(username: str) -> SelectQuery[Account]:
    return SelectQuery(
        Account,
        """
        SELECT * FROM account WHERE username = $1;
        """,
        username,
    )
