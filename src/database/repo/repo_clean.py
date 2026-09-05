from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import case, func, select, delete, and_, or_, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import aliased

from src.constants import UTC_PLUS_5, ADMINS
from src.config import settings
from src.database.connect import db
from src.database.models.model_clean import (
    AdminModel,
    BlockTypeModel,
    MessageErrorModel,
    MessageFullTextModel,
    MessageModel,
    UserBannedModel,
    UserChatBindingModel,
)


class RepoClean:
    async def get_messages_older_than(self, before_ts: int) -> list[tuple[int, int]]:
        stmt = (
            select(MessageModel.chat_id, MessageModel.message_id)
            .where(MessageModel.date_ts < before_ts)
            .order_by(MessageModel.chat_id, MessageModel.date_ts, MessageModel.message_id)
        )
        async with db.session() as session:
            res = await session.execute(stmt)
            return [(int(chat_id), int(message_id)) for chat_id, message_id in res.all()]

    async def get_unclassified_messages(
        self,
        limit: int,
        chat_id: int | None = None,
    ) -> list[dict[str, object]]:
        stmt = (
            select(
                MessageModel.chat_id,
                MessageModel.message_id,
                MessageModel.media_group_id,
                MessageFullTextModel.full_text,
                MessageModel.reply_to_message_id,
                MessageModel.image_hash,
            )
            .join(
                MessageFullTextModel,
                and_(
                    MessageFullTextModel.chat_id == MessageModel.chat_id,
                    MessageFullTextModel.message_id == MessageModel.message_id,
                ),
            )
            .where(
                MessageModel.message_type.is_(None),
                MessageModel.approved == 0,
                MessageModel.chat_id == chat_id if chat_id is not None else True,
            )
            .order_by(MessageModel.date_ts.asc(), MessageModel.message_id.asc())
            .limit(limit)
        )
        async with db.session() as session:
            rows = (await session.execute(stmt)).all()
            return [
                {
                    "chat_id": int(chat_id),
                    "message_id": int(message_id),
                    "media_group_id": media_group_id,
                    "text_full": str(full_text or ""),
                    "reply_message_id": reply_to_message_id,
                    "has_image": image_hash is not None,
                    "image_hash": image_hash,
                }
                for (
                    chat_id,
                    message_id,
                    media_group_id,
                    full_text,
                    reply_to_message_id,
                    image_hash,
                ) in rows
            ]

    async def get_noncompliant_messages(
        self,
        chat_id: int,
        limit: int = 500,
    ) -> tuple[int, list[tuple[int, int, list[int], str, int | None, str | None]]]:
        condition = or_(
            MessageModel.message_type == 4,
            and_(MessageModel.errors.is_not(None), MessageModel.errors != "[]"),
        )
        base_condition = and_(
            MessageModel.chat_id == chat_id,
            MessageModel.approved == 0,
            condition,
        )
        rows_stmt = (
            select(
                MessageModel.message_id,
                MessageModel.message_type,
                MessageModel.errors,
                MessageModel.text_short,
                MessageModel.user_id,
                MessageModel.media_group_id,
            )
            .where(base_condition)
            .order_by(MessageModel.date_ts.desc(), MessageModel.message_id.desc())
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(MessageModel).where(base_condition)
        async with db.session() as session:
            total = int((await session.execute(count_stmt)).scalar_one())
            rows = (await session.execute(rows_stmt)).all()
            return total, [
                (
                    int(message_id),
                    int(message_type or 4),
                    [int(code) for code in json.loads(errors or "[]")],
                    str(text_short or ""),
                    user_id,
                    media_group_id,
                )
                for message_id, message_type, errors, text_short, user_id, media_group_id in rows
            ]

    async def get_format_notice_recipients(
        self,
        chat_id: int,
        *,
        sent_before: str,
        limit: int = 500,
    ) -> list[tuple[int, str | None, str | None]]:
        stmt = (
            select(
                MessageModel.user_id,
                MessageModel.username,
                MessageModel.full_name,
                MessageModel.message_type,
                MessageModel.errors,
                UserBannedModel.format_notice_sent_at,
            )
            .outerjoin(UserBannedModel, UserBannedModel.user_id == MessageModel.user_id)
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.approved == 0,
                MessageModel.user_id.is_not(None),
                ~MessageModel.user_id.in_(ADMINS),
                MessageModel.errors.is_not(None),
                MessageModel.errors != "[]",
                or_(
                    UserBannedModel.user_id.is_(None),
                    UserBannedModel.block_type.is_(None),
                ),
                or_(
                    UserBannedModel.format_notice_sent_at.is_(None),
                    UserBannedModel.format_notice_sent_at == "",
                    UserBannedModel.format_notice_sent_at <= sent_before,
                ),
            )
            .order_by(MessageModel.date_ts.asc(), MessageModel.message_id.asc())
            .limit(limit)
        )
        recipients: dict[int, tuple[str | None, str | None]] = {}

        async with db.session() as session:
            rows = (await session.execute(stmt)).all()

        for user_id, username, full_name, message_type, errors, _ in rows:
            if user_id is None or message_type == 4:
                continue
            try:
                error_codes = [int(code) for code in json.loads(errors or "[]")]
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not error_codes or 4 in error_codes:
                continue
            recipients.setdefault(int(user_id), (username, full_name))

        return [(user_id, username, full_name) for user_id, (username, full_name) in recipients.items()]

    async def mark_format_notice_sent(
        self,
        user_id: int,
        *,
        sent_at: str,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        stmt = insert(UserBannedModel).values(
            user_id=user_id,
            created_at="",
            format_notice_sent_at=sent_at,
            username=username,
            full_name=full_name,
        ).on_conflict_do_update(
            index_elements=[UserBannedModel.user_id],
            set_=dict(
                format_notice_sent_at=sent_at,
                username=username,
                full_name=full_name,
            ),
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def add_notice_failed_banned_user(
        self,
        user_id: int,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC_PLUS_5).strftime("%Y-%m-%d %H:%M:%S")
        block_type = case(
            (UserBannedModel.block_type == 2, 2),
            (UserBannedModel.block_type == 3, 3),
            (UserBannedModel.block_type == 1, 1),
            else_=4,
        )
        stmt = insert(UserBannedModel).values(
            user_id=user_id,
            created_at=now,
            blocked_until=None,
            block_type=4,
            username=username,
            full_name=full_name,
        ).on_conflict_do_update(
            index_elements=[UserBannedModel.user_id],
            set_=dict(
                created_at=now,
                blocked_until=None,
                block_type=block_type,
                username=username,
                full_name=full_name,
            ),
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_invalid_messages_to_delete(
        self,
        chat_id: int,
        *,
        stale_before_ts: int,
        limit: int = 1000,
    ) -> list[tuple[int, int | None, str | None, str | None, str]]:
        stmt = (
            select(
                MessageModel.message_id,
                MessageModel.user_id,
                MessageModel.username,
                MessageModel.full_name,
                MessageModel.message_type,
                MessageModel.errors,
                MessageModel.date_ts,
            )
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.approved == 0,
                or_(
                    MessageModel.message_type == 4,
                    and_(MessageModel.errors.is_not(None), MessageModel.errors != "[]"),
                ),
            )
            .order_by(MessageModel.date_ts.asc(), MessageModel.message_id.asc())
            .limit(limit)
        )

        async with db.session() as session:
            rows = (await session.execute(stmt)).all()

        messages: list[tuple[int, int | None, str | None, str | None, str]] = []
        for message_id, user_id, username, full_name, message_type, errors, date_ts in rows:
            try:
                error_codes = [int(code) for code in json.loads(errors or "[]")]
            except (TypeError, ValueError, json.JSONDecodeError):
                error_codes = []

            is_flood = message_type == 4 or 4 in error_codes
            is_stale_format_error = bool(error_codes) and not is_flood and int(date_ts) <= stale_before_ts
            if is_flood:
                messages.append((int(message_id), user_id, username, full_name, "flood"))
            elif is_stale_format_error:
                messages.append((int(message_id), user_id, username, full_name, "invalid_ad"))

        return messages

    async def save_message_classifications(
        self,
        classifications: list[
            tuple[int, int, str, str | None, str | None, int | None, int, list[int]]
        ],
    ) -> None:
        async with db.session() as session:
            for (
                chat_id,
                message_id,
                expected_text,
                expected_image_hash,
                expected_media_group_id,
                expected_reply_id,
                message_type,
                error_codes,
            ) in classifications:
                current_stmt = (
                    select(
                        MessageFullTextModel.full_text,
                        MessageModel.image_hash,
                        MessageModel.media_group_id,
                        MessageModel.reply_to_message_id,
                    )
                    .join(
                        MessageFullTextModel,
                        and_(
                            MessageFullTextModel.chat_id == MessageModel.chat_id,
                            MessageFullTextModel.message_id == MessageModel.message_id,
                        ),
                    )
                    .where(
                        MessageModel.chat_id == chat_id,
                        MessageModel.message_id == message_id,
                        MessageModel.message_type.is_(None),
                    )
                )
                current = (await session.execute(current_stmt)).first()
                expected_fingerprint = (
                    expected_text,
                    expected_image_hash,
                    expected_media_group_id,
                    expected_reply_id,
                )
                if current is None or tuple(current) != expected_fingerprint:
                    continue

                normalized_errors = sorted(set(error_codes))
                update_result = await session.execute(
                    update(MessageModel)
                    .where(
                        MessageModel.chat_id == chat_id,
                        MessageModel.message_id == message_id,
                        MessageModel.message_type.is_(None),
                    )
                    .values(
                        message_type=message_type,
                        errors=json.dumps(normalized_errors, ensure_ascii=False),
                    )
                )
                if update_result.rowcount != 1:
                    continue
                await session.execute(
                    delete(MessageErrorModel).where(
                        MessageErrorModel.chat_id == chat_id,
                        MessageErrorModel.message_id == message_id,
                    )
                )
                if normalized_errors:
                    await session.execute(
                        insert(MessageErrorModel).values(
                            [
                                {
                                    "chat_id": chat_id,
                                    "message_id": message_id,
                                    "error_type": error_code,
                                }
                                for error_code in normalized_errors
                            ]
                        )
                    )
            await session.commit()

    async def upsert_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        text_short: str,
        text_full: str,
        text_full_hash: str | None,
        image_hash: str | None,
        media_group_id: str | None,
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
        async with db.session() as session:
            current_stmt = select(
                MessageModel.text_full_hash,
                MessageModel.image_hash,
                MessageModel.media_group_id,
                MessageModel.reply_to_message_id,
                MessageFullTextModel.full_text,
            ).outerjoin(
                MessageFullTextModel,
                and_(
                    MessageFullTextModel.chat_id == MessageModel.chat_id,
                    MessageFullTextModel.message_id == MessageModel.message_id,
                ),
            ).where(
                MessageModel.chat_id == chat_id,
                MessageModel.message_id == message_id,
            )
            current = (await session.execute(current_stmt)).first()
            fingerprint = (text_full_hash, image_hash, media_group_id, reply_to_message_id, text_full)
            changed = current is not None and tuple(current) != fingerprint

            stmt = insert(MessageModel).values(
                chat_id=chat_id,
                message_id=message_id,
                text_short=text_short,
                text_full_hash=text_full_hash,
                image_hash=image_hash,
                media_group_id=media_group_id,
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
                    media_group_id=media_group_id,
                    reply_to_message_id=reply_to_message_id,
                    original_user_id=original_user_id,
                    original_author=original_author,
                    created_at=created_at,
                    date_ts=date_ts,
                    has_keywords=has_keywords,
                    user_id=user_id,
                    username=username,
                    full_name=full_name,
                    **({"message_type": None, "errors": None, "approved": 0} if changed else {}),
                ),
            )
            await session.execute(stmt)

            full_text_stmt = insert(MessageFullTextModel).values(
                chat_id=chat_id,
                message_id=message_id,
                full_text=text_full,
            ).on_conflict_do_update(
                index_elements=[MessageFullTextModel.chat_id, MessageFullTextModel.message_id],
                set_=dict(full_text=text_full),
            )
            await session.execute(full_text_stmt)

            if changed:
                await session.execute(
                    delete(MessageErrorModel).where(
                        MessageErrorModel.chat_id == chat_id,
                        MessageErrorModel.message_id == message_id,
                    )
                )

            await session.commit()

    async def get_message_ids_without_keywords_since(self, chat_id: int, since_ts: int) -> list[int]:
        parent_message = aliased(MessageModel)
        grouped_message = aliased(MessageModel)
        parent_exists = (
            select(parent_message.message_id)
            .where(
                parent_message.chat_id == MessageModel.chat_id,
                parent_message.message_id == MessageModel.reply_to_message_id,
            )
            .exists()
        )
        same_logical_message = or_(
            and_(
                MessageModel.media_group_id.is_not(None),
                grouped_message.media_group_id == MessageModel.media_group_id,
            ),
            and_(
                MessageModel.media_group_id.is_(None),
                grouped_message.message_id == MessageModel.message_id,
            ),
        )
        group_has_keywords = (
            select(func.max(grouped_message.has_keywords))
            .where(
                grouped_message.chat_id == MessageModel.chat_id,
                grouped_message.date_ts >= since_ts,
                same_logical_message,
            )
            .scalar_subquery()
        )
        stmt = (
            select(MessageModel.message_id)
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
                or_(
                    group_has_keywords == 0,
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
        async with db.session() as session:
            await session.execute(
                delete(MessageErrorModel).where(
                    MessageErrorModel.chat_id == chat_id,
                    MessageErrorModel.message_id == message_id,
                )
            )
            await session.execute(
                delete(MessageFullTextModel).where(
                    MessageFullTextModel.chat_id == chat_id,
                    MessageFullTextModel.message_id == message_id,
                )
            )
            await session.execute(
                delete(MessageModel).where(
                    MessageModel.chat_id == chat_id,
                    MessageModel.message_id == message_id,
                )
            )
            await session.commit()

    async def delete_messages_missing_from_snapshot(
        self,
        chat_id: int,
        seen_message_ids: set[int],
        since_ts: int,
    ) -> int:
        stmt = select(MessageModel.message_id).where(
            MessageModel.chat_id == chat_id,
            MessageModel.date_ts >= since_ts,
        )
        async with db.session() as session:
            rows = await session.execute(stmt)
            missing_ids = [int(row[0]) for row in rows.all() if int(row[0]) not in seen_message_ids]

        for message_id in missing_ids:
            await self.delete_record(chat_id, message_id)
        return len(missing_ids)

    async def approve_message(
        self,
        chat_id: int,
        message_id: int,
        *,
        clear_classification: bool = False,
    ) -> None:
        values: dict[str, object] = {"approved": 1}
        if clear_classification:
            values.update(message_type=None, errors=None)

        async with db.session() as session:
            await session.execute(
                update(MessageModel)
                .where(
                    MessageModel.chat_id == chat_id,
                    MessageModel.message_id == message_id,
                )
                .values(**values)
            )
            if clear_classification:
                await session.execute(
                    delete(MessageErrorModel).where(
                        MessageErrorModel.chat_id == chat_id,
                        MessageErrorModel.message_id == message_id,
                    )
                )
            await session.commit()

    async def increment_message_violation(self, user_id: int, violation: str) -> int:
        now = datetime.now(UTC_PLUS_5).strftime("%Y-%m-%d %H:%M:%S")
        if violation == "invalid_ad":
            column = UserBannedModel.invalid_ads_count
            values = {"invalid_ads_count": 1}
            update_values = {column.key: func.coalesce(column, 0) + 1}
        elif violation == "flood":
            column = UserBannedModel.flood_count
            values = {"flood_count": 1}
            flood_count = func.coalesce(column, 0) + 1
            update_values = {
                column.key: flood_count,
                UserBannedModel.created_at.key: case(
                    (flood_count >= settings.access.flood_messages_limit, now),
                    else_=UserBannedModel.created_at,
                ),
                UserBannedModel.blocked_until.key: case(
                    (flood_count >= settings.access.flood_messages_limit, None),
                    else_=UserBannedModel.blocked_until,
                ),
                UserBannedModel.block_type.key: case(
                    (
                        and_(
                            flood_count >= settings.access.flood_messages_limit,
                            UserBannedModel.block_type == 2,
                        ),
                        2,
                    ),
                    (flood_count >= settings.access.flood_messages_limit, 3),
                    else_=UserBannedModel.block_type,
                ),
            }
        else:
            raise ValueError(f"Unknown violation type: {violation}")

        stmt = insert(UserBannedModel).values(
            user_id=user_id,
            created_at=now if violation == "flood" and settings.access.flood_messages_limit <= 1 else "",
            block_type=3 if violation == "flood" and settings.access.flood_messages_limit <= 1 else None,
            **values,
        ).on_conflict_do_update(
            index_elements=[UserBannedModel.user_id],
            set_=update_values,
        )
        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()
            if violation == "flood":
                res = await session.execute(
                    select(UserBannedModel.flood_count).where(UserBannedModel.user_id == user_id)
                )
                return int(res.scalar_one_or_none() or 0)
            if violation == "invalid_ad":
                res = await session.execute(
                    select(UserBannedModel.invalid_ads_count).where(UserBannedModel.user_id == user_id)
                )
                return int(res.scalar_one_or_none() or 0)
            return 0

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
                MessageModel.media_group_id,
            )
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
            )
            .order_by(MessageModel.date_ts.asc())
            .order_by(MessageModel.message_id.asc())
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
                    media_group_id,
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
                    media_group_id,
                ) in res.all()
            ]

    async def get_messages_for_limit_since(
        self,
        chat_id: int,
        since_ts: int,
    ) -> list[tuple[int, int, int, str | None, str | None, str | None]]:
        stmt = (
            select(
                MessageModel.message_id,
                MessageModel.date_ts,
                MessageModel.user_id,
                MessageModel.username,
                MessageModel.full_name,
                MessageModel.media_group_id,
            )
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.date_ts >= since_ts,
                MessageModel.user_id.is_not(None),
                ~MessageModel.user_id.in_(ADMINS),
            )
            .order_by(MessageModel.user_id.asc(), MessageModel.date_ts.asc(), MessageModel.message_id.asc())
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [
                (int(mid), int(ts), int(user_id), username, full_name, media_group_id)
                for mid, ts, user_id, username, full_name, media_group_id in res.all()
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

    async def mark_messages_repeated(self, chat_id: int, message_ids: list[int]) -> None:
        if not message_ids:
            return
        stmt = (
            update(MessageModel)
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.message_id.in_(message_ids),
            )
            .values(is_repeated=1)
        )
        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def clear_repeated_by_message(self, chat_id: int, message_id: int) -> list[int]:
        async with db.session() as session:
            message_ids = await self._get_logical_message_ids_in_session(session, chat_id, message_id)
            if not message_ids:
                return []

            clear_stmt = (
                update(MessageModel)
                .where(
                    MessageModel.chat_id == chat_id,
                    MessageModel.message_id.in_(message_ids),
                )
                .values(is_repeated=0)
            )
            await session.execute(clear_stmt)
            await session.commit()
            return message_ids

    async def get_logical_message_ids(self, chat_id: int, message_id: int) -> list[int]:
        async with db.session() as session:
            return await self._get_logical_message_ids_in_session(session, chat_id, message_id)

    async def _get_logical_message_ids_in_session(self, session, chat_id: int, message_id: int) -> list[int]:
        rows_stmt = (
            select(MessageModel.message_id, MessageModel.media_group_id)
            .where(MessageModel.chat_id == chat_id)
            .order_by(MessageModel.date_ts.asc(), MessageModel.message_id.asc())
        )
        rows_res = await session.execute(rows_stmt)
        rows = [(int(mid), media_group_id) for mid, media_group_id in rows_res.all()]
        selected_index = next((index for index, (mid, _) in enumerate(rows) if mid == message_id), None)
        if selected_index is None:
            return []

        selected_media_group_id = rows[selected_index][1]
        if not selected_media_group_id:
            return [message_id]

        start = selected_index
        while start > 0 and rows[start - 1][1] == selected_media_group_id:
            start -= 1

        end = selected_index
        while end + 1 < len(rows) and rows[end + 1][1] == selected_media_group_id:
            end += 1

        return [mid for mid, _ in rows[start : end + 1]]

    async def get_repeated_messages(
        self,
        chat_id: int,
    ) -> list[tuple[int, int | None, str | None, str | None, str | None]]:
        stmt = (
            select(
                MessageModel.message_id,
                MessageModel.user_id,
                MessageModel.username,
                MessageModel.full_name,
                MessageModel.media_group_id,
            )
            .where(
                MessageModel.chat_id == chat_id,
                MessageModel.is_repeated == 1,
            )
            .order_by(MessageModel.date_ts.asc(), MessageModel.message_id.asc())
        )
        async with db.session() as session:
            res = await session.execute(stmt)
            return [
                (int(mid), user_id, username, full_name, media_group_id)
                for mid, user_id, username, full_name, media_group_id in res.all()
            ]

    async def get_message_author(
        self,
        chat_id: int,
        message_id: int,
    ) -> tuple[int | None, str | None, str | None] | None:
        stmt = select(MessageModel.user_id, MessageModel.username, MessageModel.full_name).where(
            MessageModel.chat_id == chat_id,
            MessageModel.message_id == message_id,
        )
        async with db.session() as session:
            res = await session.execute(stmt)
            row = res.first()
            if not row:
                return None
            return row[0], row[1], row[2]

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

    async def get_block_types(self) -> list[tuple[int, str, str]]:
        stmt = (
            select(
                BlockTypeModel.block_type,
                BlockTypeModel.name,
                BlockTypeModel.description,
            )
            .order_by(BlockTypeModel.block_type.asc())
        )

        async with db.session() as session:
            res = await session.execute(stmt)
            return [(int(block_type), str(name), str(description)) for block_type, name, description in res.all()]

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
            (UserBannedModel.block_type == 3, 3),
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
        block_priority = case(
            (UserBannedModel.block_type == 2, 4),
            (UserBannedModel.block_type == 3, 3),
            (UserBannedModel.block_type == 1, 2),
            (UserBannedModel.block_type == 4, 1),
            else_=0,
        )
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
                block_priority.desc(),
                UserBannedModel.block_repeat_cnt.desc(),
                UserBannedModel.flood_count.desc(),
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
            .values(
                user_id=user_id,
                created_at="",
                blocked_until=None,
                is_blocked=0,
                block_type=None,
                invalid_ads_count=0,
                flood_count=0,
            )
            .on_conflict_do_update(
                index_elements=[UserBannedModel.user_id],
                set_=dict(
                    created_at="",
                    blocked_until=None,
                    is_blocked=0,
                    block_type=None,
                    invalid_ads_count=0,
                    flood_count=0,
                ),
            )
        )

        async with db.session() as session:
            await session.execute(stmt)
            await session.commit()

repo_clean = RepoClean()
