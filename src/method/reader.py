import asyncio
import csv
from telethon import TelegramClient
from telethon.tl.types import User, Channel

API_ID = 39311391
API_HASH = "cce6ce4a6a9890113098df81fd1f4f80"
SESSION_NAME = "tg_session"

# Группа: @username или ссылка. Для приватной можно передать invite-link,
# но сначала надо вступить аккаунтом.
TARGET = "https://t.me/+-dIYB8HtfgMxNTcy"

LIMIT = 5000
CSV_PATH = "history.csv"


def safe_text(s: str | None) -> str:
    return " ".join((s or "").split())


async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        phone = input("Enter phone: ")
        await client.send_code_request(phone)
        code = input("Enter code: ")
        await client.sign_in(phone, code)

    print("Authorized!")

    chat = await client.get_entity(TARGET)

    rows = []
    async for msg in client.iter_messages(chat, limit=LIMIT):
        dt = msg.date.isoformat() if msg.date else ""
        text = safe_text(msg.message)

        sender_type = "unknown"
        sender_id = None
        sender_name = ""
        sender_username = ""

        # 1) Обычный отправитель (чаще всего User)
        sender = await msg.get_sender()

        if isinstance(sender, User):
            sender_type = "user"
            sender_id = sender.id
            sender_name = " ".join(filter(None, [sender.first_name, sender.last_name]))
            sender_username = sender.username or ""

        # 2) Сообщение "от имени группы/канала" (часто анонимный админ)
        # В супергруппах Telethon даёт msg.sender_chat
        if getattr(msg, "sender_chat", None) is not None:
            sc = msg.sender_chat
            sender_type = "sender_chat"   # группа/канал (аноним)
            sender_id = sc.id
            sender_name = getattr(sc, "title", "") or ""
            sender_username = getattr(sc, "username", "") or ""

        # 3) Иногда sender бывает Channel (редко для группы, но бывает в связках)
        if isinstance(sender, Channel) and sender_type == "unknown":
            sender_type = "channel"
            sender_id = sender.id
            sender_name = getattr(sender, "title", "") or ""
            sender_username = getattr(sender, "username", "") or ""

        # 4) Сервисные сообщения (вступил/вышел/пин и т.д.) — текста может не быть
        is_service = msg.action is not None

        print(
            f"[{dt}] msg_id={msg.id} "
            f"type={sender_type} sid={sender_id} "
            f"name='{sender_name}' user='{sender_username}' "
            f"service={is_service} "
            f"text='{text[:120]}'"
        )

        rows.append({
            "date": dt,
            "msg_id": msg.id,
            "sender_type": sender_type,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "is_service": int(is_service),
            "text": text,
        })

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "msg_id",
                "sender_type",
                "sender_id",
                "sender_name",
                "sender_username",
                "is_service",
                "text",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"\nSaved {len(rows)} messages to {CSV_PATH}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())