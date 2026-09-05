from src.database.connect import db as dbconn
from src.database.models.base import Base
from src.database.models import model_clean  # важно: импорт моделей
from sqlalchemy import text

async def init_db() -> None:
    async with dbconn.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        await conn.execute(
            text(
                "INSERT OR IGNORE INTO block_types (block_type, name, description) "
                "VALUES (1, 'limit', 'Превышение лимита объявлений')"
            )
        )
        await conn.execute(
            text(
                "INSERT OR IGNORE INTO block_types (block_type, name, description) "
                "VALUES (2, 'repeat', 'Повторное объявление')"
            )
        )
        await conn.execute(
            text(
                "UPDATE block_types "
                "SET name = 'limit', description = 'Превышение лимита объявлений' "
                "WHERE block_type = 1"
            )
        )

        message_types = (
            (1, "advertisement", "Объявление о продаже или передаче"),
            (2, "clarification", "Уточнение или ответ на объявление"),
            (3, "wanted", "Покупка, поиск или просьба отдать даром"),
            (4, "off_topic", "Флуд или общение не по теме доски объявлений"),
        )
        for type_id, name, description in message_types:
            await conn.execute(
                text(
                    "INSERT INTO message_types (message_type, name, description) "
                    "VALUES (:id, :name, :description) "
                    "ON CONFLICT(message_type) DO UPDATE SET "
                    "name = excluded.name, description = excluded.description"
                ),
                {"id": type_id, "name": name, "description": description},
            )

        error_types = (
            (1, "missing_address", "Не указан адрес (адрес может быть ссылкой на карту)"),
            (2, "missing_price", "Не указана стоимость и не сказано, что товар отдаётся бесплатно"),
            (3, "missing_image", "Нет картинки в объявлении"),
            (4, "flood", "Флуд"),
        )
        for type_id, name, description in error_types:
            await conn.execute(
                text(
                    "INSERT INTO message_error_types (error_type, name, description) "
                    "VALUES (:id, :name, :description) "
                    "ON CONFLICT(error_type) DO UPDATE SET "
                    "name = excluded.name, description = excluded.description"
                ),
                {"id": type_id, "name": name, "description": description},
            )
        await conn.execute(
            text(
                "UPDATE block_types "
                "SET name = 'repeat', description = 'Повторное объявление' "
                "WHERE block_type = 2"
            )
        )
        await conn.execute(
            text(
                "INSERT OR IGNORE INTO block_types (block_type, name, description) "
                "VALUES (3, 'flood', 'Флуд')"
            )
        )
        await conn.execute(
            text(
                "UPDATE block_types "
                "SET name = 'flood', description = 'Флуд' "
                "WHERE block_type = 3"
            )
        )

        result = await conn.execute(text("PRAGMA table_info(admins)"))
        columns = {row[1] for row in result.fetchall()}

        if columns and "created_at" not in columns:
            await conn.execute(text("ALTER TABLE admins ADD COLUMN created_at TEXT"))
            await conn.execute(
                text(
                    "UPDATE admins "
                    "SET created_at = datetime(COALESCE(added_at_ts, strftime('%s', 'now')), 'unixepoch') "
                    "WHERE created_at IS NULL"
                )
            )
        elif columns and "created_at" in columns:
            await conn.execute(
                text(
                    "UPDATE admins "
                    "SET created_at = datetime(CAST(created_at AS INTEGER), 'unixepoch') "
                    "WHERE typeof(created_at) = 'integer' "
                    "OR created_at GLOB '[0-9]*'"
                )
            )

        if columns and "username" not in columns:
            await conn.execute(text("ALTER TABLE admins ADD COLUMN username TEXT"))

        if columns and "full_name" not in columns:
            await conn.execute(text("ALTER TABLE admins ADD COLUMN full_name TEXT"))

        result = await conn.execute(text("PRAGMA table_info(user_banned)"))
        user_banned_columns = {row[1] for row in result.fetchall()}

        if user_banned_columns and "cnt" in user_banned_columns and "block_repeat_cnt" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned RENAME COLUMN cnt TO block_repeat_cnt"))
            user_banned_columns.remove("cnt")
            user_banned_columns.add("block_repeat_cnt")

        if user_banned_columns and "block_repeat_cnt" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN block_repeat_cnt INTEGER DEFAULT 1"))
            await conn.execute(text("UPDATE user_banned SET block_repeat_cnt = 1 WHERE block_repeat_cnt IS NULL"))

        if user_banned_columns and "blocked_until" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN blocked_until TEXT"))

        if user_banned_columns and "is_blocked" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN is_blocked INTEGER DEFAULT 0"))
            await conn.execute(
                text(
                    "UPDATE user_banned "
                    "SET is_blocked = 1 "
                    "WHERE blocked_until IS NOT NULL AND blocked_until != ''"
                )
            )

        if user_banned_columns and "block_limit" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN block_limit INTEGER DEFAULT 0"))
            await conn.execute(text("UPDATE user_banned SET block_limit = 0 WHERE block_limit IS NULL"))

        if user_banned_columns and "block_type" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN block_type INTEGER"))
            await conn.execute(
                text(
                    "UPDATE user_banned "
                    "SET block_type = 2 "
                    "WHERE created_at IS NOT NULL AND created_at != ''"
                )
            )

        if user_banned_columns and "invalid_ads_count" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN invalid_ads_count INTEGER DEFAULT 0"))
            await conn.execute(
                text("UPDATE user_banned SET invalid_ads_count = 0 WHERE invalid_ads_count IS NULL")
            )

        if user_banned_columns and "flood_count" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN flood_count INTEGER DEFAULT 0"))
            await conn.execute(text("UPDATE user_banned SET flood_count = 0 WHERE flood_count IS NULL"))

        if user_banned_columns and "format_notice_sent_at" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN format_notice_sent_at TEXT"))

        result = await conn.execute(text("PRAGMA table_info(messages)"))
        message_columns = {row[1] for row in result.fetchall()}

        if message_columns and "message_short" in message_columns and "text_short" not in message_columns:
            await conn.execute(text("ALTER TABLE messages RENAME COLUMN message_short TO text_short"))
            message_columns.remove("message_short")
            message_columns.add("text_short")

        if message_columns and "message_hash" in message_columns and "text_full_hash" not in message_columns:
            await conn.execute(text("ALTER TABLE messages RENAME COLUMN message_hash TO text_full_hash"))
            message_columns.remove("message_hash")
            message_columns.add("text_full_hash")

        if message_columns and "text_full_hash" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN text_full_hash TEXT"))

        if message_columns and "image_hash" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN image_hash TEXT"))

        if message_columns and "media_group_id" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN media_group_id TEXT"))

        if message_columns and "reply_to_message_id" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN reply_to_message_id INTEGER"))

        if message_columns and "original_author" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN original_author TEXT"))

        if message_columns and "original_user_id" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN original_user_id BIGINT"))

        if message_columns and "is_repeated" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN is_repeated INTEGER DEFAULT 0"))
            await conn.execute(text("UPDATE messages SET is_repeated = 0 WHERE is_repeated IS NULL"))

        if message_columns and "message_type" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN message_type INTEGER"))

        if message_columns and "errors" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN errors TEXT"))

        if message_columns and "approved" not in message_columns:
            await conn.execute(text("ALTER TABLE messages ADD COLUMN approved INTEGER DEFAULT 0"))
            await conn.execute(text("UPDATE messages SET approved = 0 WHERE approved IS NULL"))

        await conn.execute(
            text(
                "INSERT OR IGNORE INTO message_full_texts (chat_id, message_id, full_text) "
                "SELECT chat_id, message_id, COALESCE(text_short, '') FROM messages"
            )
        )
