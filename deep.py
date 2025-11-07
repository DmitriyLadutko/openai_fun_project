from fastapi import FastAPI
from pydantic import BaseModel
import aiosqlite
import os
from contextlib import asynccontextmanager
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_NAME = "articles.db"
client = OpenAI(api_key=OPENAI_API_KEY)


class PromptRequest(BaseModel):
    prompt: str


async def reset_db():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            content TEXT
        )
        """)
        await db.commit()


async def save_article(prompt: str, content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO articles (prompt, content) VALUES (?, ?)", (prompt, content))
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await reset_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/generate/")
async def generate_article(request: PromptRequest):
    prompt = request.prompt

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": f"Напиши короткую статью до 200 символов по теме: {prompt}"}
        ],
        stream=False
    )
    content = response.choices[0].message.content.strip()
    await save_article(prompt, content)

    return {"prompt": prompt, "content": content}


# Просмотр всех статей
@app.get("/articles/")
async def list_articles():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, prompt, content FROM articles")
        rows = await cursor.fetchall()
        articles = [{"id": r[0], "prompt": r[1], "content": r[2]} for r in rows]
    return {"articles": articles}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "deep:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info"
    )
