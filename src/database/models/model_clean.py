from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class MessageModel(Base):
    __tablename__ = "messages"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    text_short: Mapped[str] = mapped_column(Text, default="")
    text_full_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_group_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    original_author: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text)
    date_ts: Mapped[int] = mapped_column(Integer, index=True)
    has_keywords: Mapped[int] = mapped_column(Integer, index=True)  # 0/1
    is_repeated: Mapped[int] = mapped_column(Integer, default=0, index=True)
    message_type: Mapped[int | None] = mapped_column(
        ForeignKey("message_types.message_type"), nullable=True, index=True
    )
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # опционально (если хочешь хранить автора)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class MessageFullTextModel(Base):
    __tablename__ = "message_full_texts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_id", "message_id"],
            ["messages.chat_id", "messages.message_id"],
            ondelete="CASCADE",
        ),
    )

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_text: Mapped[str] = mapped_column(Text, default="")


class MessageTypeModel(Base):
    __tablename__ = "message_types"

    message_type: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class MessageErrorTypeModel(Base):
    __tablename__ = "message_error_types"

    error_type: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class MessageErrorModel(Base):
    __tablename__ = "message_errors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_id", "message_id"],
            ["messages.chat_id", "messages.message_id"],
            ondelete="CASCADE",
        ),
    )

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    error_type: Mapped[int] = mapped_column(
        ForeignKey("message_error_types.error_type"), primary_key=True
    )


class UserChatBindingModel(Base):
    __tablename__ = "user_chat_bindings"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    bound_at_ts: Mapped[int] = mapped_column(Integer)


class AdminModel(Base):
    __tablename__ = "admins"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    added_at_ts: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class BlockTypeModel(Base):
    __tablename__ = "block_types"

    block_type: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class UserBannedModel(Base):
    __tablename__ = "user_banned"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_until: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_blocked: Mapped[int] = mapped_column(Integer, default=0)
    block_repeat_cnt: Mapped[int] = mapped_column(Integer, default=1)
    block_limit: Mapped[int] = mapped_column(Integer, default=0)
    invalid_ads_count: Mapped[int] = mapped_column(Integer, default=0)
    flood_count: Mapped[int] = mapped_column(Integer, default=0)
    format_notice_sent_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
