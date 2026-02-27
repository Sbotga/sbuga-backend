from database.models import Account, AccountPermission
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


def get_permissions(account_id: int) -> SelectQuery[AccountPermission]:
    return SelectQuery(
        AccountPermission,
        "SELECT * FROM account_permissions WHERE account_id = $1",
        account_id,
    )


def has_permission(account_id: int, permission: str) -> SelectQuery[AccountPermission]:
    return SelectQuery(
        AccountPermission,
        "SELECT * FROM account_permissions WHERE account_id = $1 AND permission = $2",
        account_id,
        permission,
    )
