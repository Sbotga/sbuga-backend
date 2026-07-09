"""Manage bot accounts and account permissions.

A bot is a normal `account` row plus a `bot_account` token record, so permissions
(`account_permissions`) and alias authorship (`created_by`) work identically for
bots and humans — every subcommand below accepts either.

    python -m scripts.manage_accounts create-bot sysbuga
    python -m scripts.manage_accounts grant sysbuga manage_aliases
    python -m scripts.manage_accounts permissions sysbuga
    python -m scripts.manage_accounts list-bots
    python -m scripts.manage_accounts rotate-token sysbuga
    python -m scripts.manage_accounts revoke sysbuga manage_aliases
    python -m scripts.manage_accounts delete-bot sysbuga

`<target>` is an account id, a username, or a bot name.
"""

import argparse
import asyncio
import secrets
import sys
import time
from pathlib import Path

import asyncpg
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db  # noqa: E402
from helpers.bot_tokens import generate_bot_token, hash_bot_token  # noqa: E402
from helpers.passwords import hash_password  # noqa: E402

EPOCH_OFFSET = 1600218000000


def _new_account_id() -> int:
    """Same snowflake scheme the signup route uses."""
    timestamp_bits = int(time.time() * 1000) - EPOCH_OFFSET
    return (timestamp_bits << 22) | secrets.randbits(22)


async def _connect() -> asyncpg.Pool:
    with open("config.yml", "r") as f:
        config = yaml.load(f, yaml.Loader)
    cfg = config["psql"]
    return await asyncpg.create_pool(
        host=cfg["host"],
        user=cfg["user"],
        database=cfg["database"],
        password=cfg["password"],
        port=cfg["port"],
        min_size=1,
        max_size=2,
        ssl="disable",
    )


async def _fetchrow(conn, query):
    row = await conn.fetchrow(query.sql, *query.args)
    return query.model.model_validate(dict(row)) if row else None


async def _fetch(conn, query):
    rows = await conn.fetch(query.sql, *query.args)
    return [query.model.model_validate(dict(r)) for r in rows]


async def _execute(conn, query):
    return await conn.execute(query.sql, *query.args)


async def _resolve_account_id(conn, target: str) -> int:
    """An account id, a username, or a bot name."""
    if target.isdigit():
        account = await _fetchrow(conn, db.accounts.get_account_by_id(int(target)))
        if account:
            return account.id
    account = await _fetchrow(conn, db.accounts.get_account_by_username(target))
    if account:
        return account.id
    bot = await _fetchrow(conn, db.bots.get_bot_by_name(target))
    if bot:
        return bot.account_id
    sys.exit(f"No account, username, or bot named {target!r}")


# --- commands ---


async def create_bot(conn, name: str) -> None:
    if await _fetchrow(conn, db.bots.get_bot_by_name(name)):
        sys.exit(f"Bot {name!r} already exists")

    username = f"bot_{name}"
    if await _fetchrow(conn, db.accounts.get_account_by_username(username)):
        sys.exit(f"Username {username!r} is taken")

    account_id = _new_account_id()
    token = generate_bot_token()

    # An unusable random password + a non-routable email: bots can never log in
    # through the normal flow, only via their token.
    async with conn.transaction():
        await _execute(
            conn,
            db.accounts.create_account(
                account_id,
                f"{name}@bots.invalid",
                name,
                username,
                hash_password(secrets.token_urlsafe(32)),
            ),
        )
        await conn.execute(
            "UPDATE account SET email_verified = TRUE WHERE id = $1", account_id
        )
        await _execute(
            conn, db.bots.create_bot_account(account_id, name, hash_bot_token(token))
        )

    print(f"Created bot {name!r} (account id {account_id})")
    print(f"\n  {token}\n")
    print("This token is shown ONCE. Store it in the bot's config as `bot_token`.")
    print("Send it as:  Authorization: Bot <token>")


async def rotate_token(conn, name: str) -> None:
    bot = await _fetchrow(conn, db.bots.get_bot_by_name(name))
    if not bot:
        sys.exit(f"No bot named {name!r}")
    token = generate_bot_token()
    await _execute(
        conn, db.bots.rotate_bot_token(bot.account_id, hash_bot_token(token))
    )
    print(f"Rotated token for {name!r} (old token is now invalid)")
    print(f"\n  {token}\n")


async def delete_bot(conn, name: str) -> None:
    bot = await _fetchrow(conn, db.bots.get_bot_by_name(name))
    if not bot:
        sys.exit(f"No bot named {name!r}")
    # deleting the account cascades to bot_account + account_permissions,
    # and nulls created_by on any aliases it added
    await _execute(conn, db.accounts.delete_account(bot.account_id))
    print(f"Deleted bot {name!r} (account id {bot.account_id}) and its permissions")


async def set_revoked(conn, name: str, revoked: bool) -> None:
    bot = await _fetchrow(conn, db.bots.get_bot_by_name(name))
    if not bot:
        sys.exit(f"No bot named {name!r}")
    await _execute(conn, db.bots.set_bot_revoked(bot.account_id, revoked))
    print(f"{'Revoked' if revoked else 'Re-enabled'} bot {name!r}")


async def list_bots(conn) -> None:
    rows = await _fetch(conn, db.bots.list_bots())
    if not rows:
        print("No bots.")
        return
    for bot in rows:
        perms = await _fetch(conn, db.accounts.get_permissions(bot.account_id))
        flag = " [REVOKED]" if bot.revoked else ""
        names = ", ".join(p.permission for p in perms) or "none"
        print(f"{bot.name}{flag}  account_id={bot.account_id}  permissions: {names}")


async def grant(conn, target: str, permission: str) -> None:
    account_id = await _resolve_account_id(conn, target)
    await _execute(conn, db.accounts.add_permission(account_id, permission))
    print(f"Granted {permission!r} to {target} (account id {account_id})")


async def revoke(conn, target: str, permission: str) -> None:
    account_id = await _resolve_account_id(conn, target)
    await _execute(conn, db.accounts.remove_permission(account_id, permission))
    print(f"Revoked {permission!r} from {target} (account id {account_id})")


async def permissions(conn, target: str) -> None:
    account_id = await _resolve_account_id(conn, target)
    perms = await _fetch(conn, db.accounts.get_permissions(account_id))
    if not perms:
        print(f"{target} (account id {account_id}) has no permissions")
        return
    print(f"{target} (account id {account_id}):")
    for p in perms:
        print(f"  - {p.permission}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-bot", help="Create a bot account and print its token")
    p.add_argument("name")

    p = sub.add_parser("rotate-token", help="Issue a new token, invalidating the old")
    p.add_argument("name")

    p = sub.add_parser("delete-bot", help="Delete a bot account and its permissions")
    p.add_argument("name")

    p = sub.add_parser("revoke-bot", help="Disable a bot without deleting it")
    p.add_argument("name")

    p = sub.add_parser("enable-bot", help="Re-enable a revoked bot")
    p.add_argument("name")

    sub.add_parser("list-bots", help="List bots and their permissions")

    p = sub.add_parser("grant", help="Grant a permission to a user or bot")
    p.add_argument("target", help="account id, username, or bot name")
    p.add_argument("permission")

    p = sub.add_parser("revoke", help="Revoke a permission from a user or bot")
    p.add_argument("target", help="account id, username, or bot name")
    p.add_argument("permission")

    p = sub.add_parser("permissions", help="List a user's or bot's permissions")
    p.add_argument("target", help="account id, username, or bot name")

    return parser


async def main() -> None:
    args = build_parser().parse_args()
    pool = await _connect()
    async with pool.acquire() as conn:
        if args.command == "create-bot":
            await create_bot(conn, args.name)
        elif args.command == "rotate-token":
            await rotate_token(conn, args.name)
        elif args.command == "delete-bot":
            await delete_bot(conn, args.name)
        elif args.command == "revoke-bot":
            await set_revoked(conn, args.name, True)
        elif args.command == "enable-bot":
            await set_revoked(conn, args.name, False)
        elif args.command == "list-bots":
            await list_bots(conn)
        elif args.command == "grant":
            await grant(conn, args.target, args.permission)
        elif args.command == "revoke":
            await revoke(conn, args.target, args.permission)
        elif args.command == "permissions":
            await permissions(conn, args.target)
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
