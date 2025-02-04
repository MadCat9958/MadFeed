import asyncio
import json
import logging
import os
import sqlite3
import sys
import traceback

import aiogram
from aiogram import F, exceptions, filters, types
from dotenv import load_dotenv

load_dotenv()

bot = aiogram.Bot(token=os.getenv("BOT_TOKEN"))
dp = aiogram.Dispatcher()
db = sqlite3.connect("messages.db", autocommit=True)
db.row_factory = sqlite3.Row
cur = db.cursor()
media_groups: dict[list[types.Message]] = {}
MEDIA_GROUPS_FETCH_COOLDOWN = 0.6

locales = {}
for locale in os.scandir("./locales"):
    if not locale.name.endswith(".json") or not locale.is_file():
        continue
    locales[locale.name[:-5]] = json.load(open(locale.path))

cur.execute(
    """CREATE TABLE IF NOT EXISTS messages (
        msg_id BIGINT NOT NULL,
        sender_id BIGINT NOT NULL,
        original_message_id BIGINT NOT NULL
    );"""
)
cur.execute(  # i created it for future button interactions (yeah, this note is for dementia)
    """CREATE TABLE IF NOT EXISTS media_groups (
        media_group_id BIGINT NOT NULL,
        msg_id BIGINT NOT NULL
    );"""
)
cur.execute(
    """CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT NOT NULL,
        is_banned BOOLEAN NOT NULL DEFAULT(false)
    );"""
)
# msg_id - Message ID for getting message instance
# sender_id - User ID, who sent the message
# original_message_id - Original message ID in suggester's dialog


@dp.message(filters.CommandStart())
async def command_start_handler(message: types.Message):
    await message.reply(
        locales.get(message.from_user.language_code, locales["default"])[
            "start_command_message"
        ]
    )


def check_banned(user_id: int):
    user = cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return user is not None and user["is_banned"]


@dp.message(F.from_user.id == int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id, filters.Command("ban"))
async def ban_user(message: types.Message):
    args = message.text.split()[1:]
    if len(args) == 0 and message.reply_to_message is None:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "not_enough_arguments"
            ]
        )
    if len(args) > 0 and message.reply_to_message is not None:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "too_many_arguments"
            ]
        )
    msg = None
    if message.reply_to_message is not None:
        cur.execute(
            "SELECT * FROM messages WHERE msg_id = ?",
            (message.reply_to_message.message_id,),
        )
        msg = cur.fetchone()
    if (len(args) > 0 and not args[0].isdigit()) or (message.reply_to_message is not None and msg is None):
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "invalid_arguments"
            ]
        )
    user_id = int(args[0]) if len(args) > 0 else msg["sender_id"]
    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )
    usr_db = cur.fetchone()
    if usr_db is None:
        cur.execute("INSERT INTO users (user_id, is_banned) VALUES (?, ?)", (user_id, True))
    elif usr_db["is_banned"]:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "already_banned"
            ]
        )
    else:
        cur.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (True, user_id))
    
    await message.reply(
        locales.get(message.from_user.language_code, locales["default"])["success"][
            "user_banned"
        ]
    )


@dp.message(F.from_user.id == int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id, filters.Command("unban"))
async def unban_user(message: types.Message):
    args = message.text.split()[1:]
    if len(args) == 0 and message.reply_to_message is None:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "not_enough_arguments"
            ]
        )
    if len(args) > 0 and message.reply_to_message is not None:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "too_many_arguments"
            ]
        )
    msg = None
    if message.reply_to_message is not None:
        cur.execute(
            "SELECT * FROM messages WHERE msg_id = ?",
            (message.reply_to_message.message_id,),
        )
        msg = cur.fetchone()
    if (len(args) > 0 and not args[0].isdigit()) or (message.reply_to_message is not None and msg is None):
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "invalid_arguments"
            ]
        )
    user_id = int(args[0]) if len(args) > 0 else msg["sender_id"]
    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )
    usr_db = cur.fetchone()
    if usr_db is None or not usr_db["is_banned"]:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "already_unbanned"
            ]
        )
    else:
        cur.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (False, user_id))
    
    await message.reply(
        locales.get(message.from_user.language_code, locales["default"])["success"][
            "user_unbanned"
        ]
    )


@dp.message(
    filters.Command("cleardb"), F.from_user.id == int(os.getenv("BOT_OWNER_ID"))
)
async def clear_db(message: types.Message):
    cur.execute("DELETE FROM messages")
    await message.reply(
        locales.get(message.from_user.language_code, locales["default"])["success"][
            "database_cleared"
        ]
    )


@dp.message(
    F.from_user.id != int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id
)
async def resend_message(message: types.Message):
    if check_banned(message.from_user.id):
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "banned"
            ]
        )
    owner_id = int(os.getenv("BOT_OWNER_ID"))
    if message.media_group_id is None:
        msg = await message.forward(owner_id)
        cur.execute(
            """INSERT INTO messages (msg_id, sender_id, original_message_id) VALUES (?, ?, ?)""",
            (msg.message_id, message.from_user.id, message.message_id),
        )
        await msg.reply(
            f"Отправитель: {message.from_user.full_name} (ID: {message.from_user.id})"
        )  # hardcoded (feature)
        await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["success"][
                "sent_to_moderation"
            ]
        )
        return
    if media_groups.get(message.media_group_id, None) is not None:
        media_groups[message.media_group_id].append(message)
        return
    media_groups[message.media_group_id] = [message]
    await asyncio.sleep(MEDIA_GROUPS_FETCH_COOLDOWN)
    origs_ids = [m.message_id for m in media_groups[message.media_group_id]]
    msgs = await bot.forward_messages(owner_id, message.chat.id, origs_ids)
    for count, msg in enumerate(msgs):
        cur.execute(
            """INSERT INTO messages (msg_id, sender_id, original_message_id) VALUES (?, ?, ?)""",
            (msg.message_id, message.from_user.id, origs_ids[count]),
        )
    await bot.send_message(
        owner_id,
        f"Отправитель: {message.from_user.full_name} (ID: {message.from_user.id})",
        reply_parameters=types.ReplyParameters(message_id=msgs[0].message_id),
    )  # hardcoded (feature)
    del media_groups[message.media_group_id]
    await message.reply(
        locales.get(message.from_user.language_code, locales["default"])["success"][
            "sent_to_moderation"
        ]
    )


@dp.message(
    F.from_user.id == int(os.getenv("BOT_OWNER_ID")), F.from_user.id == F.chat.id
)
async def answer_message(message: types.Message):
    logging.debug(message)
    logging.debug(message.reply_to_message)
    if message.reply_to_message is None:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "invalid_message"
            ]
        )
    cur.execute(
        "SELECT * FROM messages WHERE msg_id = ?",
        (message.reply_to_message.message_id,),
    )
    msg = cur.fetchone()
    if msg is None:
        return await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "suggestor_not_found"
            ]
        )
    reply_to = types.ReplyParameters(message_id=msg["original_message_id"])
    if message.media_group_id is None:
        try:
            await message.copy_to(msg["sender_id"], reply_parameters=reply_to)
        except Exception as e:
            if (
                isinstance(e, exceptions.TelegramBadRequest)
                and "message to be replied not found" in e.message
            ):
                try:
                    await message.copy_to(msg["sender_id"])
                except Exception as e:
                    await message.reply(
                        locales.get(
                            message.from_user.language_code, locales["default"]
                        )["errors"]["reply_failed"]
                    )
                    traceback.print_exc()
                else:
                    await message.reply(
                        locales.get(
                            message.from_user.language_code, locales["default"]
                        )["success"]["answer_to_suggestor_sent"]
                    )
                return
            await message.reply(
                locales.get(message.from_user.language_code, locales["default"])[
                    "errors"
                ]["reply_failed"]
            )
            traceback.print_exc()
        else:
            await message.reply(
                locales.get(message.from_user.language_code, locales["default"])[
                    "success"
                ]["answer_to_suggestor_sent"]
            )
        return
    if media_groups.get(message.media_group_id, None) is not None:
        media_groups[message.media_group_id].append(message)
        return
    media_groups[message.media_group_id] = [message]
    await asyncio.sleep(MEDIA_GROUPS_FETCH_COOLDOWN)
    origs_ids = [m.message_id for m in media_groups[message.media_group_id]]
    try:
        await bot.copy_messages(msg["sender_id"], message.chat.id, origs_ids)
    except Exception:
        await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["errors"][
                "reply_failed"
            ]
        )
        traceback.print_exc()
    else:
        await message.reply(
            locales.get(message.from_user.language_code, locales["default"])["success"][
                "answer_to_suggestor_sent"
            ]
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
