from database.query import ExecutableQuery


def delete_account(account_id: int) -> ExecutableQuery:
    return ExecutableQuery(
        """
        DELETE FROM account
        WHERE id = $1;
        """,
        account_id,
    )


def remove_permission(account_id: int, permission: str) -> ExecutableQuery:
    return ExecutableQuery(
        "DELETE FROM account_permissions WHERE account_id = $1 AND permission = $2",
        account_id,
        permission,
    )


def remove_all_permissions(account_id: int) -> ExecutableQuery:
    return ExecutableQuery(
        "DELETE FROM account_permissions WHERE account_id = $1",
        account_id,
    )
