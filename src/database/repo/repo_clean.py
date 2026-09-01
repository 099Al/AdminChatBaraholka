from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select, delete, and_, or_
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import aliased

from src.constants import UTC_PLUS_5, ADMINS
from src.database.connect import db
from src.database.models.model_clean import (
    AdminModel,
    MessageModel,
    UserBannedModel,
    UserChatBindingModel,
)


class RepoClean:
    async def upsert_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        text_short: str,
        text_full_hash: str | None,
        image_hash: str | None,
        reply_to_message_id: int | None,
        original_user_id: int | None,
        original_author: str | None,
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
            text_short=text_short,
            text_full_hash=text_full_hash,
            image_hash=image_hash,
            reply_to_message_id=reply_to_message_id,
            original_user_id=original_user_id,
            original_author=original_author,
            created_at=created_at,
            date_ts=date_ts,
            has_keywords=has_keywords,
            user_id=user_id,
            username=username,
            full_name=full_name,
        ).on_conflict_do_update(
            index_elements=[MessageModel.chat_id, MessageModel.message_id],
            set_=dict(
                text_short=text_short,
                text_full_hash=text_full_hash,
                image_hash=image_hash,
                reply_to_message_id=reply_to_message_id,
                original_user_id=original_user_id,
                original_author=original_author,
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
        parent_message = aliased(MessageModel)
        parent_exists = (
            select(parent_message.message_id)
            .where(
                parent_message.chat_id == MessageModel.chat_id,
                parent_message.message_id == MessageModel.reply_to_message_id,
            )
            .exists()
        )
        stmt = (
            select(MessageModel.message_id)
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
                or_(
                    MessageModel.has_keywords == 0,
                    func.lower(MessageModel.text_short).like("%удаленное сообщение%"),
                    func.lower(MessageModel.text_short).like("%удалённое сообщение%"),
                    and_(
                        MessageModel.reply_to_message_id.is_not(None),
                        ~parent_exists,
                    ),
                ),
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

    async def get_messages_since(
        self,
        chat_id: int,
        since_ts: int,
    ) -> list[
        tuple[
            int,
            int,
            str,
            str | None,
            str | None,
            int | None,
            int | None,
            int | None,
            str | None,
            str | None,
        ]
    ]:
        """
        Возвращает список сообщений за период.
        """
        stmt = (
            select(
                MessageModel.message_id,
                MessageModel.date_ts,
                MessageModel.text_short,
                MessageModel.text_full_hash,
                MessageModel.image_hash,
                MessageModel.reply_to_message_id,
                MessageModel.original_user_id,
                MessageModel.user_id,
                MessageModel.username,
                MessageModel.full_name,
            )
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
            )
            .order_by(MessageModel.date_ts.asc())
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [
                (
                    int(mid),
                    int(ts),
                    str(text or ""),
                    text_full_hash,
                    image_hash,
                    reply_to_message_id,
                    original_user_id,
                    user_id,
                    username,
                    full_name,
                )
                for (
                    mid,
                    ts,
                    text,
                    text_full_hash,
                    image_hash,
                    reply_to_message_id,
                    original_user_id,
                    user_id,
                    username,
                    full_name,
                ) in res.all()
            ]

    async def get_messages_for_limit_since(
        self,
        chat_id: int,
        since_ts: int,
    ) -> list[tuple[int, int, int, str | None, str | None]]:
        stmt = (
            select(
                MessageModel.message_id,
                MessageModel.date_ts,
                MessageModel.user_id,
                MessageModel.username,
                MessageModel.full_name,
            )
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
                MessageModel.user_id.is_not(None),
                ~MessageModel.user_id.in_(ADMINS),
            )
            .order_by(MessageModel.user_id.asc(), MessageModel.date_ts.asc())
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [
                (int(mid), int(ts), int(user_id), username, full_name)
                for mid, ts, user_id, username, full_name in res.all()
            ]

    async def add_admin(
        self,
        user_id: int,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC_PLUS_5)
        stmt = insert(AdminModel).values(
            user_id=user_id,
            added_at_ts=int(now.timestamp()),
            created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
            username=username,
            full_name=full_name,
        ).on_conflict_do_nothing(
            index_elements=[AdminModel.user_id],
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def remove_admin(self, user_id: int) -> None:
        stmt = delete(AdminModel).where(AdminModel.user_id == user_id)

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def is_admin(self, user_id: int) -> bool:
        stmt = select(AdminModel.user_id).where(AdminModel.user_id == user_id)

        async with db.session() as session:
            res = await session.execute(stmt)
            return res.first() is not None

    async def get_admins(self) -> list[tuple[int, str | None, str | None, str]]:
        stmt = (
            select(
                AdminModel.user_id,
                AdminModel.username,
                AdminModel.full_name,
                AdminModel.created_at,
            )
            .order_by(AdminModel.user_id.asc())
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [
                (int(user_id), username, full_name, str(created_at))
                for user_id, username, full_name, created_at in res.all()
            ]

    async def add_banned_user(
        self,
        user_id: int,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC_PLUS_5)
        stmt = insert(UserBannedModel).values(
            user_id=user_id,
            created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
            blocked_until=None,
            block_type=2,
            block_repeat_cnt=1,
            username=username,
            full_name=full_name,
        ).on_conflict_do_update(
            index_elements=[UserBannedModel.user_id],
            set_=dict(
                created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                blocked_until=None,
                block_type=2,
                block_repeat_cnt=func.coalesce(UserBannedModel.block_repeat_cnt, 0) + 1,
                username=username,
                full_name=full_name,
            ),
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def add_limit_banned_user(
        self,
        user_id: int,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC_PLUS_5)
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        block_type = case(
            (UserBannedModel.block_type == 2, 2),
            else_=1,
        )
        stmt = insert(UserBannedModel).values(
            user_id=user_id,
            created_at=created_at,
            blocked_until=None,
            block_type=1,
            block_limit=1,
            block_repeat_cnt=0,
            username=username,
            full_name=full_name,
        ).on_conflict_do_update(
            index_elements=[UserBannedModel.user_id],
            set_=dict(
                created_at=created_at,
                blocked_until=None,
                block_type=block_type,
                block_limit=func.coalesce(UserBannedModel.block_limit, 0) + 1,
                username=username,
                full_name=full_name,
            ),
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_banned_users(
        self,
    ) -> list[tuple[int, str | None, str | None, str | None, str | None, int, int | None, int, int]]:
        stmt = (
            select(
                UserBannedModel.user_id,
                UserBannedModel.username,
                UserBannedModel.full_name,
                UserBannedModel.created_at,
                UserBannedModel.blocked_until,
                UserBannedModel.is_blocked,
                UserBannedModel.block_type,
                UserBannedModel.block_repeat_cnt,
                UserBannedModel.block_limit,
            )
            .where(
                or_(
                    and_(
                        UserBannedModel.created_at.is_not(None),
                        UserBannedModel.created_at != "",
                    ),
                    UserBannedModel.blocked_until.is_not(None),
                    UserBannedModel.is_blocked == 1,
                    UserBannedModel.block_type.is_not(None),
                )
            )
            .order_by(
                UserBannedModel.block_type.desc(),
                UserBannedModel.block_repeat_cnt.desc(),
                UserBannedModel.block_limit.desc(),
                UserBannedModel.user_id.asc(),
            )
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [
                (
                    int(user_id),
                    username,
                    full_name,
                    created_at,
                    blocked_until,
                    int(is_blocked or 0),
                    block_type,
                    int(block_repeat_cnt or 0),
                    int(block_limit or 0),
                )
                for (
                    user_id,
                    username,
                    full_name,
                    created_at,
                    blocked_until,
                    is_blocked,
                    block_type,
                    block_repeat_cnt,
                    block_limit,
                ) in res.all()
            ]

    async def set_user_blocked(
        self,
        user_id: int,
        *,
        created_at: str,
        blocked_until: str,
    ) -> None:
        stmt = (
            insert(UserBannedModel)
            .values(
                user_id=user_id,
                created_at=created_at,
                blocked_until=blocked_until,
                is_blocked=1,
            )
            .on_conflict_do_update(
                index_elements=[UserBannedModel.user_id],
                set_=dict(created_at=created_at, blocked_until=blocked_until, is_blocked=1),
            )
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def clear_user_block(self, user_id: int) -> None:
        stmt = (
            insert(UserBannedModel)
            .values(user_id=user_id, created_at="", blocked_until=None, is_blocked=0, block_type=None)
            .on_conflict_do_update(
                index_elements=[UserBannedModel.user_id],
                set_=dict(created_at="", blocked_until=None, is_blocked=0, block_type=None),
            )
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

repo_clean = RepoClean()
