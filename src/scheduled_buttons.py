from __future__ import annotations

import argparse
import asyncio

from aiogram import Bot

from src.config import settings
from src.database.connect import db
from src.database.models.setup import init_db
from src.database.repo.repo_clean import repo_clean
from src.services.scheduled_buttons import (
    format_schedule_status_plain,
    scheduled_buttons_runner,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run scheduled admin button tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="start scheduler loop")
    start_parser.add_argument("--group-chat-id", type=int)
    start_parser.add_argument("--notify-chat-id", type=int)

    run_once_parser = subparsers.add_parser("run-once", help="run all scheduled tasks once")
    run_once_parser.add_argument("--group-chat-id", type=int)
    run_once_parser.add_argument("--notify-chat-id", type=int)

    subparsers.add_parser("status", help="print schedule status table")
    return parser


async def _resolve_group_chat_id(value: int | None) -> int:
    if value is not None:
        return value
    if settings.access.scheduled_group_chat_id is not None:
        return settings.access.scheduled_group_chat_id

    bound_chat_id = await repo_clean.get_user_active_chat(settings.access.main_admin_user)
    if bound_chat_id is None:
        raise RuntimeError(
            "Group chat is not configured. Set SCHEDULED_GROUP_CHAT_ID or bind a group with /bind as MAIN_ADMIN_USER."
        )
    return bound_chat_id


def _resolve_notify_chat_id(value: int | None) -> int:
    if value is not None:
        return value
    if settings.access.scheduled_notify_chat_id is not None:
        return settings.access.scheduled_notify_chat_id
    return settings.access.main_admin_user


async def _main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    await init_db()
    bot: Bot | None = None
    try:
        if args.command == "status":
            print(await format_schedule_status_plain())
            return

        group_chat_id = await _resolve_group_chat_id(args.group_chat_id)
        notify_chat_id = _resolve_notify_chat_id(args.notify_chat_id)
        bot = Bot(token=settings.token.BOT_TOKEN)

        if args.command == "run-once":
            results = await scheduled_buttons_runner.run_once(
                bot,
                group_chat_id=group_chat_id,
                notify_chat_id=notify_chat_id,
            )
            print("\n\n".join(results))
            return

        print("Scheduler start is temporarily disabled.")
        return

        # next_run = await scheduled_buttons_runner.start(
        #     bot,
        #     group_chat_id=group_chat_id,
        #     notify_chat_id=notify_chat_id,
        # )
        # print(f"Scheduler started. Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        # print("Press Ctrl+C to stop.")
        # await asyncio.Event().wait()
    finally:
        if bot is not None:
            await bot.session.close()
        await db.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("Scheduler stopped.")
