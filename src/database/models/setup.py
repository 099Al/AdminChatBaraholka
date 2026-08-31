from src.database.connect import db as dbconn
from src.database.models.base import Base
from src.database.models import model_clean  # важно: импорт моделей
from sqlalchemy import text

async def init_db() -> None:
    async with dbconn.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

        if user_banned_columns and "cnt" not in user_banned_columns:
            await conn.execute(text("ALTER TABLE user_banned ADD COLUMN cnt INTEGER DEFAULT 1"))
            await conn.execute(text("UPDATE user_banned SET cnt = 1 WHERE cnt IS NULL"))

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
