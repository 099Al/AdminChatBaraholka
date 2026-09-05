from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import (
    button_2_txt,
    button_3_txt,
    button_4_txt,
    button_5_txt,
    button_6_txt,
    button_7_txt,
    button_8_txt,
)
from src.handlers.start_buttons.button_1_find_invalid_messages import run_find_invalid_messages
from src.handlers.start_buttons.button_2_delete_repeats import run_find_repeat_messages
from src.handlers.start_buttons.button_4_block_users import run_block_banned_users
from src.handlers.start_buttons.button_5_delete_limit import run_delete_limit_messages
from src.handlers.start_buttons.button_5_send_format_notices import run_send_format_notices
from src.handlers.start_buttons.button_6_delete_marked_repeats import run_delete_marked_repeat_messages
from src.handlers.start_buttons.button_7_delete_invalid_messages import run_delete_invalid_messages

WINDOW_START_HOUR = 10
WINDOW_END_HOUR = 22
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TELEGRAM_MESSAGE_LIMIT = 3900


@dataclass(frozen=True)
class ScheduledButtonTask:
    key: str
    title: str
    run: Callable[..., Awaitable[str]]


TASKS = (
    ScheduledButtonTask("02_find_repeats", button_2_txt, run_find_repeat_messages),
    ScheduledButtonTask("03_delete_limit", button_3_txt, run_delete_limit_messages),
    ScheduledButtonTask("04_find_invalid", button_4_txt, run_find_invalid_messages),
    ScheduledButtonTask("05_send_notices", button_5_txt, run_send_format_notices),
    ScheduledButtonTask("06_delete_repeats", button_6_txt, run_delete_marked_repeat_messages),
    ScheduledButtonTask("07_delete_invalid", button_7_txt, run_delete_invalid_messages),
    ScheduledButtonTask("08_block_users", button_8_txt, run_block_banned_users),
)


def _format_dt(value: datetime | None) -> str | None:
    return value.strftime(DATETIME_FORMAT) if value else None


def _truncate_message(text: str) -> str:
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return text
    return text[: TELEGRAM_MESSAGE_LIMIT - 20] + "\n...обрезано"


def calculate_next_run(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC_PLUS_5)
    interval_hours = settings.access.scheduled_run_interval_hours
    day_start = current.replace(hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
    day_end = current.replace(hour=WINDOW_END_HOUR, minute=0, second=0, microsecond=0)

    if current <= day_start:
        return day_start

    next_run = day_start
    while next_run < current:
        next_run += timedelta(hours=interval_hours)

    if next_run <= day_end:
        return next_run

    return day_start + timedelta(days=1)


class ScheduledButtonsRunner:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._run_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, bot: Bot, *, group_chat_id: int, notify_chat_id: int) -> datetime:
        next_run = calculate_next_run()
        await self._store_next_run(next_run)
        if not self.is_running:
            self._task = asyncio.create_task(
                self._loop(bot, group_chat_id=group_chat_id, notify_chat_id=notify_chat_id)
            )
        return next_run

    async def stop(self) -> bool:
        if not self.is_running or self._task is None:
            return False
        if self._run_lock.locked():
            return False

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        return True

    async def _loop(self, bot: Bot, *, group_chat_id: int, notify_chat_id: int) -> None:
        while True:
            next_run = calculate_next_run()
            await self._store_next_run(next_run)
            await asyncio.sleep(max(0.0, (next_run - datetime.now(UTC_PLUS_5)).total_seconds()))
            await self.run_once(bot, group_chat_id=group_chat_id, notify_chat_id=notify_chat_id)

    async def run_once(self, bot: Bot, *, group_chat_id: int, notify_chat_id: int | None = None) -> list[str]:
        if self._run_lock.locked():
            return ["Предыдущий запуск еще выполняется."]

        async with self._run_lock:
            next_run = calculate_next_run(datetime.now(UTC_PLUS_5) + timedelta(seconds=1))
            results: list[str] = []
            for scheduled_task in TASKS:
                started_at = datetime.now(UTC_PLUS_5)
                status = "ok"
                try:
                    if scheduled_task.key in {"02_find_repeats", "04_find_invalid"}:
                        result = await scheduled_task.run(
                            bot,
                            group_chat_id=group_chat_id,
                            review_chat_id=notify_chat_id,
                        )
                    else:
                        result = await scheduled_task.run(bot, group_chat_id=group_chat_id)
                except Exception as error:
                    result = f"Ошибка: {error}"
                    status = "error"

                await repo_clean.upsert_scheduled_task_run(
                    task_key=scheduled_task.key,
                    title=scheduled_task.title,
                    last_run_at=_format_dt(started_at),
                    next_run_at=_format_dt(next_run),
                    last_status=status,
                )
                results.append(f"{scheduled_task.title}: {result}")

            if notify_chat_id is not None:
                try:
                    await bot.send_message(
                        notify_chat_id,
                        _truncate_message("Плановый запуск завершен.\n\n" + "\n\n".join(results)),
                    )
                except TelegramRetryAfter as error:
                    await asyncio.sleep(error.retry_after + 0.5)
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass

            return results

    async def _store_next_run(self, next_run: datetime) -> None:
        current_rows = {
            task_key: (last_run_at, last_status)
            for task_key, _, last_run_at, _, last_status in await repo_clean.get_scheduled_task_runs()
        }
        for scheduled_task in TASKS:
            last_run_at, last_status = current_rows.get(scheduled_task.key, (None, None))
            await repo_clean.upsert_scheduled_task_run(
                task_key=scheduled_task.key,
                title=scheduled_task.title,
                last_run_at=last_run_at,
                next_run_at=_format_dt(next_run),
                last_status=last_status,
            )


async def format_schedule_status() -> str:
    return "<pre>" + escape(await format_schedule_status_plain()) + "</pre>"


async def format_schedule_status_plain() -> str:
    rows = await repo_clean.get_scheduled_task_runs()
    if not rows:
        next_run = _format_dt(calculate_next_run())
        rows = [(task.key, task.title, None, next_run, None) for task in TASKS]

    table_rows = ["Задача                         | Последний запуск    | Следующий запуск"]
    table_rows.append("-------------------------------+---------------------+---------------------")
    for _, title, last_run_at, next_run_at, _ in rows:
        table_rows.append(f"{title[:29]:29} | {last_run_at or '-':19} | {next_run_at or '-':19}")

    return "\n".join(table_rows)


scheduled_buttons_runner = ScheduledButtonsRunner()
