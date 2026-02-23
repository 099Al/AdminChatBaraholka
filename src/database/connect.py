from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.config import settings

class DBConnect:

    def __init__(self):
        self.engine = create_async_engine(settings.db.db_url, echo=False, future=True)
        self._sessionmaker = async_sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)


    def session(self):
        """
        Использование:
        async with db.session() as session:
            ...
        """
        return self._sessionmaker()

    async def dispose(self):
        """Корректное закрытие пула соединений"""
        await self.engine.dispose()


db = DBConnect()