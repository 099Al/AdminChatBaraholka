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
