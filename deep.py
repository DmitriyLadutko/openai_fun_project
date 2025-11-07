from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aiosqlite
import os
from contextlib import asynccontextmanager
from openai import OpenAI, PermissionDeniedError
from dotenv import load_dotenv
import logging

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_NAME = "articles.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

class PromptRequest(BaseModel):
    prompt: str

async def reset_db():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        logger.info("Старая база удалена")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            content TEXT
        )
        """)
        await db.commit()
        logger.info("Создана новая таблица")

async def save_article(prompt: str, content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO articles (prompt, content) VALUES (?, ?)", (prompt, content))
        await db.commit()
        logger.info("Статья сохранена в базе")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await reset_db()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/generate/")
async def generate_article(request: PromptRequest):
    prompt = request.prompt
    try:
        response = await client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": f"Напиши короткую статью до 200 символов по теме: {prompt}"}
            ],
        )
        content = response.choices[0].message.content.strip()
        await save_article(prompt, content)
        logger.info(f"Статья сгенерирована по теме: {prompt}")
        return {"prompt": prompt, "content": content}

    except PermissionDeniedError:
        logger.error(r""" 
                     _     ____  _____   ____    ____  ____  ____ ___  ____  _   _      ____  _                                                            
                    / \ /\/ ___\/  __/  /  _ \  /  __\/  __\/  _ \\  \//\  \//  / \__/|/  _ \/ \  /|                                                       
                    | | |||    \|  \    | / \|  |  \/||  \/|| / \| \  /  \  /   | |\/||| / \|| |\ ||                                                       
                    | \_/|\___ ||  /_   | |-||  |  __/|    /| \_/| /  \  / /    | |  ||| |-||| | \||                                                       
                    \____/\____/\____\  \_/ \|  \_/   \_/\_\\____//__/\\/_/     \_/  \|\_/ \|\_/  \|_                                                      
                                                                                                                                                    
                     ____  _____ ____ ____  _     ____  _____   ____  ____  _____ _      ____  _    ____  ____  _____   _____ ____  _____ ____  _  __ ____ 
                    /  _ \/  __//   _Y  _ \/ \ /\/ ___\/  __/  /  _ \/  __\/  __// \  /|/  _ \/ \  /  _ \/  __\/  __/  /    //  __\/  __//  _ \/ |/ // ___\
                    | | //|  \  |  / | / \|| | |||    \|  \    | / \||  \/||  \  | |\ ||| / \|| |  | / \||  \/||  \    |  __\|  \/||  \  | / \||   / |    \
                    | |_\\|  /_ |  \_| |-||| \_/|\___ ||  /_   | \_/||  __/|  /_ | | \||| |-||| |  | |-|||    /|  /_   | |   |    /|  /_ | |-|||   \ \___ |
                    \____/\____\\____|_/ \|\____/\____/\____\  \____/\_/   \____\\_/  \|\_/ \|\_/  \_/ \|\_/\_\\____\  \_/   \_/\_\\____\\_/ \|\_|\_\\____/
""")
        raise HTTPException(status_code=403, detail="Доступ к OpenAI запрещён")
    except Exception as e:
        logger.error(f"Ошибка при генерации: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/articles/")
async def list_articles():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, prompt, content FROM articles")
        rows = await cursor.fetchall()
        articles = [{"id": r[0], "prompt": r[1], "content": r[2]} for r in rows]
    logger.info(f"Выдано {len(articles)} статей")
    return {"articles": articles}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("deep:app", host="127.0.0.1", port=8001, reload=True, log_level="info")
