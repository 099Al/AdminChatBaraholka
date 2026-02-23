from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert

from src.constants import UTC_PLUS_5, ADMINS
from src.database.connect import db
from src.database.models.model_clean import MessageModel, UserChatBindingModel


class RepoClean:
    async def upsert_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        message_short: str,
        message_hash: str,
        created_at: str,
        date_ts: int,
        has_keywords: int,
        user_id: int | None = None,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        stmt = insert(MessageModel).values(
            chat_id=chat_id,
            message_id=message_id,
            message_short=message_short,
            message_hash=message_hash,
            created_at=created_at,
            date_ts=date_ts,
            has_keywords=has_keywords,
            user_id=user_id,
            username=username,
            full_name=full_name,
        ).on_conflict_do_update(
            index_elements=[MessageModel.chat_id, MessageModel.message_id],
            set_=dict(
                message_short=message_short,
                message_hash=message_hash,
                created_at=created_at,
                date_ts=date_ts,
                has_keywords=has_keywords,
                user_id=user_id,
                username=username,
                full_name=full_name,
            ),
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_message_ids_without_keywords_since(self, chat_id: int, since_ts: int) -> list[int]:
        stmt = (
            select(MessageModel.message_id)
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
                MessageModel.has_keywords == 0,
                ~MessageModel.user_id.in_(ADMINS),
            )
            .order_by(MessageModel.date_ts.asc())
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [row[0] for row in res.all()]

    async def delete_record(self, chat_id: int, message_id: int) -> None:
        stmt = delete(MessageModel).where(
            MessageModel.chat_id == chat_id,
            MessageModel.message_id == message_id,
        )
        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def set_user_active_chat(self, user_id: int, chat_id: int) -> None:
        stmt = insert(UserChatBindingModel).values(
            user_id=user_id,
            chat_id=chat_id,
            bound_at_ts=datetime.now(UTC_PLUS_5),
        ).on_conflict_do_update(
            index_elements=[UserChatBindingModel.user_id],
            set_=dict(chat_id=chat_id, bound_at_ts=datetime.now(UTC_PLUS_5)),
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_user_active_chat(self, user_id: int) -> int | None:
        stmt = select(UserChatBindingModel.chat_id).where(UserChatBindingModel.user_id == user_id)
        async with db.session() as session:
            res = await session.execute(stmt)
            row = res.first()
            return int(row[0]) if row else None

    async def get_messages_since(self, chat_id: int, since_ts: int) -> list[tuple[int, int, str]]:
        """
        Возвращает список (message_id, date_ts, message_short) за период.
        """
        stmt = (
            select(MessageModel.message_id, MessageModel.date_ts, MessageModel.message_short)
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
            )
            .order_by(MessageModel.date_ts.asc())
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [(int(mid), int(ts), str(text or "")) for (mid, ts, text) in res.all()]

repo_clean = RepoClean()