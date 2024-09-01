import aiogram
import os
import sys
import asyncio
import logging
import sqlite3
import traceback
import json

from dotenv import load_dotenv
from aiogram import filters, F
from aiogram import types

load_dotenv()

bot = aiogram.Bot(token=os.getenv("BOT_TOKEN"))
dp = aiogram.Dispatcher()
db = sqlite3.connect("messages.db", autocommit=True)
db.row_factory = sqlite3.Row
cur = db.cursor()

locales = {}
for locale in os.scandir("./locales"):
    if not locale.name.endswith(".json") or not locale.is_file(): continue
    locales[locale.name[:-5]] = json.load(open(locale.path))

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
    await message.reply(locales.get(message.from_user.language_code, locales["default"])["start_command_message"])

@dp.message(filters.Command("cleardb"), F.from_user.id == int(os.getenv("BOT_OWNER_ID")))
async def clear_db(message: types.Message):
    cur.execute("DELETE FROM messages")
    await message.reply(locales.get(message.from_user.language_code, locales["default"])["success"]["database_cleared"])

@dp.message(F.from_user.id != int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id)
async def resend_message(message: types.Message):
    owner_id = int(os.getenv("BOT_OWNER_ID"))
    msg = await message.forward(owner_id,)
    cur.execute(
        """INSERT INTO messages (msg_id, sender_id, original_message_id) VALUES (?, ?, ?)""",
        (msg.message_id, message.from_user.id, message.message_id)
    )
    await msg.reply(f"Отправитель: {message.from_user.full_name} (ID: {message.from_user.id})") # hardcoded (feature)
    await message.reply(locales.get(message.from_user.language_code, locales["default"])["success"]["sent_to_moderation"])

@dp.message(F.from_user.id == int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id)
async def answer_message(message: types.Message):
    if message.reply_to_message is None:
        return await message.reply(locales.get(message.from_user.language_code, locales["default"])["errors"]["invalid_message"])
    cur.execute("SELECT * FROM messages WHERE msg_id = ?", (message.reply_to_message.message_id,))
    msg = cur.fetchone()
    if msg is None:
        return await message.reply(locales.get(message.from_user.language_code, locales["default"])["errors"]["suggestor_not_found"])
    try:
        await message.copy_to(msg["sender_id"])
    except:
        await message.reply(locales.get(message.from_user.language_code, locales["default"])["errors"]["reply_failed"])
        traceback.print_exc()
    else:
        await message.reply(locales.get(message.from_user.language_code, locales["default"])["success"]["answer_to_suggestor_sent"])

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())