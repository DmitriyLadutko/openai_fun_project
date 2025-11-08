import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI
from dotenv import load_dotenv

# --- Загружаем ключи из .env ---
load_dotenv()
BOT_TOKEN = os.getenv("TG_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
# --- Память пользователей ---
user_modes = {}

# --- Клавиатуры ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Текст"), KeyboardButton(text="🖼 Изображение")],
        ],
        resize_keyboard=True
    )

def get_back_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="↩️ Назад в меню")],
        ],
        resize_keyboard=True
    )

# --- Команда /start ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_modes[message.from_user.id] = "menu"
    await message.answer(
        "👋 Привет! Я бот с OpenAI.\n\nВыбери режим работы:",
        reply_markup=get_main_menu()
    )

# --- Выбор режима ---
@dp.message(F.text.in_(["💬 Текст", "🖼 Изображение"]))
async def mode_selected(message: types.Message):
    mode = "text" if "Текст" in message.text else "image"
    user_modes[message.from_user.id] = mode

    await message.answer(
        f"✅ Режим *{message.text}* активирован!\n\n"
        f"Теперь отправь запрос, например:\n"
        f"👉 {'Расскажи шутку' if mode == 'text' else 'Нарисуй котика'}",
        parse_mode="Markdown",
        reply_markup=get_back_menu()
    )

# --- Возврат в меню ---
@dp.message(F.text == "↩️ Назад в меню")
async def back_to_menu(message: types.Message):
    user_modes[message.from_user.id] = "menu"
    await message.answer(
        "🔙 Возврат в главное меню. Выбери режим:",
        reply_markup=get_main_menu()
    )

# --- Обработка запросов ---
@dp.message()
async def process_message(message: types.Message):
    user_id = message.from_user.id
    mode = user_modes.get(user_id, "menu")
    query = message.text.strip()

    if mode == "menu":
        await message.answer("👇 Пожалуйста, выбери режим:", reply_markup=get_main_menu())
        return

    if mode == "text":
        await message.answer("✍️ Думаю над ответом...")
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты дружелюбный Telegram-помощник."},
                    {"role": "user", "content": query},
                ]
            )
            answer = resp.choices[0].message.content
            await message.answer(answer)
        except Exception as e:
            await message.answer(f"⚠️ Ошибка: {e}")

    elif mode == "image":
        await message.answer("🎨 Рисую изображение...")
        try:
            result = await client.images.generate(
                model="gpt-image-1",
                prompt=query,
                size="1024x1024"
            )
            image_url = result.data[0].url
            await message.answer_photo(photo=image_url, caption="Готово! 😊")
        except Exception as e:
            await message.answer(f"⚠️ Ошибка при генерации изображения: {e}")

# --- Запуск ---
async def main():
    logger.info("✅ Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
