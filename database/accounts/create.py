from database.query import ExecutableQuery
from helpers.emails import get_base_email


def create_account(
    account_id: int, email: str, display_name: str, username: str, salted_password: str
) -> ExecutableQuery:
    return ExecutableQuery(
        """
        INSERT INTO account (id, email, base_email, display_name, username, salted_password)
        VALUES ($1, $2, $3, $4);
        """,
        email,
        get_base_email(email),
        account_id,
        display_name,
        username,
        salted_password,
    )


def add_permission(account_id: int, permission: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        INSERT INTO account_permissions (account_id, permission)
        VALUES ($1, $2)
        ON CONFLICT (account_id, permission) DO NOTHING
        """,
        account_id,
        permission,
    )
