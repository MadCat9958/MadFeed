import aiogram
import os
import sys
import asyncio
import logging

from dotenv import load_dotenv
from aiogram import filters
from aiogram import types

load_dotenv()

bot = aiogram.Bot(token=os.getenv("BOT_TOKEN"))
dp = aiogram.Dispatcher()

@dp.message()
async def command_start_handler(message: types.Message):
    await message.reply(
        "Привет! На данный момент, бот не работает. Однако скоро ты сможешь предлагать посты в @MadCat9958 любого типа. "
        "Для удобства, будет возможность отдельно написать свой комментарий к посту, который, в зависимости от содержания, будет либо отправлен вместе с постом, либо нет.\n\n"
        "А пока что, задонать плиз: @MadDonate_bot :)"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())