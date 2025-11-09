import asyncio
import os
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI
from dotenv import load_dotenv

# --- Настройка логов ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Загрузка токенов ---
load_dotenv()
BOT_TOKEN = os.getenv("TG_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    logger.error("BOT_TOKEN и OPENAI_API_KEY должны быть установлены в .env")
    raise SystemExit("Не найдены токены")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

DB_BOT_PATH = os.getenv("DB_BOT_PATH")

# --- Создание таблиц для историй ---
async def init_db():
    async with aiosqlite.connect(DB_BOT_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_text_history (
                user_id INTEGER,
                role TEXT,
                content TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_image_history (
                user_id INTEGER,
                content TEXT
            )
        """)
        await db.commit()

# --- Клавиатуры ---
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Текст"), KeyboardButton(text="🖼 Изображение")]
        ],
        resize_keyboard=True
    )

def back_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="↩️ Назад в меню")]],
        resize_keyboard=True
    )

# --- Режим пользователей ---
user_modes = {}

# --- Работа с текстовой историей 10 последних---
async def get_text_history(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_BOT_PATH) as db:
        cursor = await db.execute(
            "SELECT role, content FROM user_text_history WHERE user_id = ? ORDER BY rowid DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        # возвращаем в прямом порядке (старые сообщения первыми)
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def add_text_history(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_BOT_PATH) as db:
        await db.execute(
            "INSERT INTO user_text_history (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )
        await db.commit()

async def clear_text_history(user_id: int):
    async with aiosqlite.connect(DB_BOT_PATH) as db:
        await db.execute("DELETE FROM user_text_history WHERE user_id = ?", (user_id,))
        await db.commit()

# --- Работа с историей изображений ---
async def get_image_history(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_BOT_PATH) as db:
        cursor = await db.execute(
            "SELECT content FROM user_image_history WHERE user_id = ? ORDER BY rowid DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [r[0] for r in reversed(rows)]

async def add_image_history(user_id: int, content: str):
    async with aiosqlite.connect(DB_BOT_PATH) as db:
        await db.execute(
            "INSERT INTO user_image_history (user_id, content) VALUES (?, ?)",
            (user_id, content)
        )
        await db.commit()

async def clear_image_history(user_id: int):
    async with aiosqlite.connect(DB_BOT_PATH) as db:
        await db.execute("DELETE FROM user_image_history WHERE user_id = ?", (user_id,))
        await db.commit()

# --- Команда /start ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    user_modes[user_id] = "menu"
    await clear_text_history(user_id)
    await clear_image_history(user_id)
    await message.answer(
        "👋 Привет! Я бот с OpenAI. Выбери режим работы:",
        reply_markup=main_menu()
    )

# --- Выбор режима ---
@dp.message(F.text.in_(["💬 Текст", "🖼 Изображение"]))
async def select_mode(message: types.Message):
    user_id = message.from_user.id
    mode = "text" if "Текст" in message.text else "image"
    user_modes[user_id] = mode

    # смена режима - чистка контекста
    if mode == "text":
        await clear_text_history(user_id)
        await add_text_history(user_id, "system", "Ты дружелюбный Telegram-помощник.")
    else:
        await clear_image_history(user_id)

    await message.answer(
        f"✅ Режим *{message.text}* активирован.\nОтправь запрос:",
        parse_mode="Markdown",
        reply_markup=back_menu()
    )

# --- Возврат в меню ---
@dp.message(F.text == "↩️ Назад в меню")
async def back_to_menu(message: types.Message):
    user_id = message.from_user.id
    user_modes[user_id] = "menu"
    await clear_text_history(user_id)
    await clear_image_history(user_id)
    await message.answer("🔙 Возврат в главное меню:", reply_markup=main_menu())

# --- Основная логика ---
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    query = message.text.strip()
    mode = user_modes.get(user_id, "menu")

    if mode == "menu":
        await message.answer("👇 Выбери режим работы:", reply_markup=main_menu())
        return

    # --- Текстовый режим ---
    if mode == "text":
        await message.answer("✍️ Думаю над ответом...")
        await add_text_history(user_id, "user", query)

        messages = await get_text_history(user_id)

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            answer = response.choices[0].message.content
            await add_text_history(user_id, "assistant", answer)
            await message.answer(answer)
        except Exception as e:
            await message.answer(f"⚠️ Ошибка: {e}")

    # --- Режим изображений ---
    elif mode == "image":
        await message.answer("🎨 Генерирую изображение...")
        await add_image_history(user_id, query)

        # последние 10 запросов пользователя
        history = await get_image_history(user_id)
        prompt = "\n".join(history)

        try:
            result = await client.images.generate(
                model="gpt-image-1",
                prompt=f"Создай изображение по описанию:\n{prompt}",
                size="1024x1024"
            )
            image_url = result.data[0].url
            await message.answer_photo(photo=image_url, caption="Готово! 😊")
        except Exception as e:
            await message.answer(f"⚠️ Ошибка: {e}")

# --- Запуск бота ---
async def main():
    await init_db()
    logger.info("✅ Бот запущен и готов к работе.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
