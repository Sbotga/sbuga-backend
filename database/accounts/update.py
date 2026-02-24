from database.query import ExecutableQuery
from typing import Optional


def update_account_password(account_id: int, salted_password: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        UPDATE account
        SET salted_password = $2, updated_at = NOW(), valid_session_uuid = gen_random_uuid()::TEXT
        WHERE id = $1;
        """,
        account_id,
        salted_password,
    )


def update_account_username(account_id: int, username: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        UPDATE account
        SET username = $2, updated_at = NOW()
        WHERE id = $1;
        """,
        account_id,
        username,
    )


def update_account_display_name(account_id: int, display_name: str) -> ExecutableQuery:
    return ExecutableQuery(
        """
        UPDATE account
        SET display_name = $2, updated_at = NOW()
        WHERE id = $1;
        """,
        account_id,
        display_name,
    )


def update_description(account_id: int, description: str) -> ExecutableQuery:
    return ExecutableQuery(
        "UPDATE accounts SET description = $1 WHERE id = $2",
        description,
        account_id,
    )


def update_profile_hash(
    account_id: int, profile_hash: Optional[str]
) -> ExecutableQuery:
    return ExecutableQuery(
        "UPDATE accounts SET profile_hash = $1 WHERE id = $2",
        profile_hash,
        account_id,
    )


def update_banner_hash(account_id: int, banner_hash: Optional[str]) -> ExecutableQuery:
    return ExecutableQuery(
        "UPDATE accounts SET banner_hash = $1 WHERE id = $2",
        banner_hash,
        account_id,
    )
