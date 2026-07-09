from database.models import BotAccount
from database.query import SelectQuery


def get_bot_by_token_hash(token_hash: str) -> SelectQuery[BotAccount]:
    return SelectQuery(
        BotAccount,
        "SELECT * FROM bot_account WHERE token_hash = $1 AND revoked = FALSE",
        token_hash,
    )


def get_bot_by_name(name: str) -> SelectQuery[BotAccount]:
    return SelectQuery(
        BotAccount,
        "SELECT * FROM bot_account WHERE name = $1",
        name,
    )


def get_bot_by_account_id(account_id: int) -> SelectQuery[BotAccount]:
    return SelectQuery(
        BotAccount,
        "SELECT * FROM bot_account WHERE account_id = $1",
        account_id,
    )


def list_bots() -> SelectQuery[BotAccount]:
    return SelectQuery(
        BotAccount,
        "SELECT * FROM bot_account ORDER BY created_at",
    )
