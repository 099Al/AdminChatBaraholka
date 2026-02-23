from src.database.connect import db as dbconn
from src.database.models.base import Base
from src.database.models import model_clean  # важно: импорт моделей

async def init_db() -> None:
    async with dbconn.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)