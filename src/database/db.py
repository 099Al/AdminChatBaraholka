import asyncio

import aiosqlite
from dataclasses import dataclass
from datetime import datetime

from src.config import settings
from src.constants import UTC_PLUS_5


@dataclass
class StoredMessage:
    chat_id: int
    message_id: int
    message_short: str
    created_at: datetime
    date_ts: int
    has_keywords: int  # 0/1
    user_id: int
    username: str
    full_name: str


class DB:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    chat_id     INTEGER NOT NULL,
                    message_id  INTEGER NOT NULL,
                    message_short TEXT,
                    created_at  DATETIME,
                    date_ts     INTEGER NOT NULL,
                    has_keywords INTEGER NOT NULL,
                    user_id     INTEGER,
                    username    TEXT,
                    full_name   TEXT,
                    PRIMARY KEY (chat_id, message_id)
                )
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(chat_id, date_ts)")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_chat_bindings (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    bound_at_ts INTEGER NOT NULL
                )
            """)
            await db.commit()


            await db.commit()

    async def upsert_message(self, msg: StoredMessage) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO messages (chat_id, message_id, message_short, created_at, date_ts, has_keywords, user_id, username, full_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, message_id) DO UPDATE SET
                    message_short=excluded.message_short,
                    created_at=excluded.created_at,
                    date_ts=excluded.date_ts,
                    has_keywords=excluded.has_keywords,
                    user_id=excluded.user_id,
                    username=excluded.username,
                    full_name=excluded.full_name
                """,
                (msg.chat_id, msg.message_id, msg.message_short, msg.created_at, msg.date_ts, msg.has_keywords, msg.user_id, msg.username, msg.full_name),
            )
            await db.commit()

    async def get_message_ids_without_keywords_since(self, chat_id: int, since_ts: int) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT message_id
                FROM messages
                WHERE chat_id = ?
                  AND date_ts >= ?
                  AND has_keywords = 0
                ORDER BY date_ts ASC
                """,
                (chat_id, since_ts),
            )
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def delete_record(self, chat_id: int, message_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM messages WHERE chat_id = ? AND message_id = ?",
                (chat_id, message_id),
            )
            await db.commit()

    async def set_user_active_chat(self, user_id: int, chat_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            bound_at_ts: int = int(datetime.now(UTC_PLUS_5).timestamp())
            await db.execute(
                """
                INSERT INTO user_chat_bindings (user_id, chat_id, bound_at_ts)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    bound_at_ts=excluded.bound_at_ts
                """,
                (user_id, chat_id, bound_at_ts),
            )
            await db.commit()

    async def get_user_active_chat(self, user_id: int) -> int | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT chat_id FROM user_chat_bindings WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else None


