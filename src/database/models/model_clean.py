from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class MessageModel(Base):
    __tablename__ = "messages"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    message_short: Mapped[str] = mapped_column(Text, default="")
    message_hash: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text)
    date_ts: Mapped[int] = mapped_column(Integer, index=True)
    has_keywords: Mapped[int] = mapped_column(Integer, index=True)  # 0/1

    # опционально (если хочешь хранить автора)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserChatBindingModel(Base):
    __tablename__ = "user_chat_bindings"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    bound_at_ts: Mapped[int] = mapped_column(Integer)