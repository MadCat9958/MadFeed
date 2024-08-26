import aiogram
import os
import sys
import asyncio
import logging
import sqlite3
import traceback

from dotenv import load_dotenv
from aiogram import filters, F
from aiogram import types

load_dotenv()

bot = aiogram.Bot(token=os.getenv("BOT_TOKEN"))
dp = aiogram.Dispatcher()
db = sqlite3.connect("messages.db", autocommit=True)
db.row_factory = sqlite3.Row
cur = db.cursor()

cur.execute(
    """CREATE TABLE IF NOT EXISTS messages (
        msg_id BIGINT NOT NULL,
        sender_id BIGINT NOT NULL,
        original_message_id BIGINT NOT NULL
    );"""
)
# msg_id - Message ID for getting message instance
# sender_id - User ID, who sent the message
# original_message_id - Original message ID in suggester's dialog 

@dp.message(filters.CommandStart())
async def command_start_handler(message: types.Message):
    await message.reply(
        "Привет! На данный момент, бот работает в ограниченном режиме. Однако скоро ты сможешь удобно предлагать посты в @MadCat9958 любого типа. "
        "Для удобства, будет возможность отдельно написать свой комментарий к посту, который, в зависимости от содержания, будет либо отправлен вместе с постом, либо нет.\n\n"
        "А пока что, задонать плиз: @MadDonate_bot :)"
    )

@dp.message(filters.Command("cleardb"), F.from_user.id == int(os.getenv("BOT_OWNER_ID")))
async def clear_db(message: types.Message):
    cur.execute("DELETE FROM messages")
    await message.reply("База данных почищена!")

@dp.message(F.from_user.id != int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id)
async def resend_message(message: types.Message):
    owner_id = int(os.getenv("BOT_OWNER_ID"))
    msg = await message.forward(owner_id,)
    cur.execute(
        """INSERT INTO messages (msg_id, sender_id, original_message_id) VALUES (?, ?, ?)""",
        (msg.message_id, message.from_user.id, message.message_id)
    )
    await msg.reply(f"Отправитель: {message.from_user.full_name} (ID: {message.from_user.id})")
    await message.reply("Переслано!")

@dp.message(F.from_user.id == int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id)
async def answer_message(message: types.Message):
    if message.reply_to_message is None:
        return await message.reply("Невозможно ответить на данное сообщение: это не предложка.")
    cur.execute("SELECT * FROM messages WHERE msg_id = ?", (message.reply_to_message.message_id,))
    msg = cur.fetchone()
    if msg is None:
        return await message.reply("Невозможно ответить на данное сообщение: нет информации об предложившем пользователе.")
    try:
        await message.copy_to(msg["sender_id"])
    except:
        await message.reply("Ответ не был отправлен! Возможно, пользователь заблокировал бота либо он больше не существует.")
        traceback.print_exc()
    else:
        await message.reply("Ответ отправлен!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())