import os
import json
import sqlite3
import httpx
import numpy as np
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai

# ── Конфиг ──────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_KEY_HERE")
CPP_BACKEND_URL = os.getenv("CPP_BACKEND_URL", "http://localhost:8080")
DB_PATH = os.getenv("DB_PATH", "archive.db")

genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel("gemini-2.0-flash")

app = FastAPI(title="Голос из архива", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory vector store (для хакатона — простота важнее) ─────────────
# Структура: [{"chunk_id": int, "text": str, "embedding": np.array}]
VECTOR_STORE: list[dict] = []


# ── БД ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
                       CREATE TABLE IF NOT EXISTS persons (
                                                              id INTEGER PRIMARY KEY,
                                                              full_name TEXT NOT NULL,
                                                              birth_year INTEGER,
                                                              death_year INTEGER,
                                                              region TEXT,
                                                              district TEXT,
                                                              occupation TEXT,
                                                              charge TEXT,
                                                              arrest_date TEXT,
                                                              sentence TEXT,
                                                              sentence_date TEXT,
                                                              rehabilitation_date TEXT,
                                                              biography TEXT,
                                                              source TEXT,
                                                              status TEXT DEFAULT 'pending'
                       );
                       CREATE TABLE IF NOT EXISTS documents (
                                                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                filename TEXT NOT NULL,
                                                                content TEXT,
                                                                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                       );
                       CREATE TABLE IF NOT EXISTS chunks (
                                                             id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                             document_id INTEGER REFERENCES documents(id),
                           chunk_text TEXT NOT NULL,
                           chunk_index INTEGER
                           );
                       """)
    conn.commit()
    conn.close()


# ── Helpers ──────────────────────────────────────────────────────────────
async def call_cpp_backend(text: str, chunk_size: int = 1000, overlap: int = 100) -> dict:
    """Отправляет текст в C++ backend, получает чанки."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{CPP_BACKEND_URL}/process",
            json={"text": text, "chunk_size": chunk_size, "overlap": overlap}
        )
        resp.raise_for_status()
        return resp.json()


def get_embedding(text: str) -> np.ndarray:
    """Получает эмбеддинг через Gemini."""
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document"
    )
    return np.array(result["embedding"], dtype=np.float32)


def get_query_embedding(text: str) -> np.ndarray:
    """Эмбеддинг для поискового запроса."""
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_query"
    )
    return np.array(result["embedding"], dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def search_similar_chunks(query_embedding: np.ndarray, top_k: int = 5) -> list[dict]:
    """Поиск похожих чанков по косинусному сходству."""
    if not VECTOR_STORE:
        return []
    scores = [
        (cosine_similarity(query_embedding, item["embedding"]), item)
        for item in VECTOR_STORE
    ]
    scores.sort(key=lambda x: x[0], reverse=True)
    return [{"score": s, "text": item["text"]} for s, item in scores[:top_k]]


# ── Startup ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    print("БД инициализирована")


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Проверка состояния сервиса."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            cpp_resp = await client.get(f"{CPP_BACKEND_URL}/health")
            cpp_ok = cpp_resp.status_code == 200
    except Exception:
        cpp_ok = False
    return {
        "status": "ok",
        "cpp_backend": "ok" if cpp_ok else "недоступен",
        "chunks_in_memory": len(VECTOR_STORE),
    }


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Загружает документ:
    1. Отправляет текст в C++ backend для чанкинга
    2. Создаёт эмбеддинги через Gemini
    3. Сохраняет в БД и in-memory vector store
    """
    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    # Шаг 1: чанкинг через C++
    cpp_result = await call_cpp_backend(text)
    if cpp_result.get("is_garbage"):
        raise HTTPException(400, f"Документ отклонён: {cpp_result.get('reason')}")

    chunks: list[str] = cpp_result["chunks"]
    if not chunks:
        raise HTTPException(400, "Документ пуст после очистки")

    # Шаг 2: сохраняем документ в БД
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO documents (filename, content) VALUES (?, ?)",
        (file.filename, text)
    )
    doc_id = cur.lastrowid

    # Шаг 3: эмбеддинги + сохранение чанков
    for i, chunk_text in enumerate(chunks):
        conn.execute(
            "INSERT INTO chunks (document_id, chunk_text, chunk_index) VALUES (?, ?, ?)",
            (doc_id, chunk_text, i)
        )
        # Получаем chunk_id
        chunk_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        embedding = get_embedding(chunk_text)
        VECTOR_STORE.append({
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "filename": file.filename,
            "text": chunk_text,
            "embedding": embedding,
        })

    conn.commit()
    conn.close()

    return {
        "filename": file.filename,
        "doc_id": doc_id,
        "chunks_count": len(chunks),
        "stats": cpp_result.get("stats", {}),
    }


class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    language: str = "auto"  # "ru", "kg", "auto"


@app.post("/api/ask")
async def ask(req: AskRequest):
    """
    RAG-запрос:
    1. Эмбеддинг вопроса
    2. Поиск релевантных чанков
    3. Генерация ответа через Gemini
    """
    if not req.question.strip():
        raise HTTPException(400, "Вопрос не может быть пустым")

    # Шаг 1: эмбеддинг вопроса
    query_emb = get_query_embedding(req.question)

    # Шаг 2: поиск похожих чанков
    results = search_similar_chunks(query_emb, top_k=req.top_k)

    if not results:
        return {
            "answer": "Документы ещё не загружены. Сначала загрузите архивные документы через /api/documents/upload",
            "sources": [],
        }

    # Шаг 3: формируем контекст для LLM
    context = "\n\n---\n\n".join(
        f"[Релевантность: {r['score']:.2f}]\n{r['text']}"
        for r in results
    )

    prompt = f"""Ты — архивный ассистент проекта «Голос из архива». 
Ты помогаешь людям узнавать о судьбах репрессированных в Кыргызстане в 1918–1953 годах.

Отвечай на языке вопроса (если вопрос на кыргызском — отвечай на кыргызском).
Отвечай только на основе предоставленных документов. 
Если информации нет — так и скажи, не придумывай.
Будь точным и уважительным к памяти людей.

ДОКУМЕНТЫ ИЗ АРХИВА:
{context}

ВОПРОС: {req.question}

ОТВЕТ:"""

    response = llm.generate_content(prompt)
    answer = response.text

    return {
        "answer": answer,
        "sources": [
            {"score": r["score"], "excerpt": r["text"][:200] + "..."}
            for r in results
        ],
    }


@app.get("/api/persons")
async def list_persons(
        region: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
):
    """Список репрессированных из БД."""
    conn = get_db()
    query = "SELECT id, full_name, birth_year, death_year, region, occupation, charge, rehabilitation_date FROM persons"
    params = []
    if region:
        query += " WHERE region = ?"
        params.append(region)
    query += f" LIMIT {limit} OFFSET {offset}"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/persons/{person_id}")
async def get_person(person_id: int):
    """Карточка конкретного репрессированного."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM persons WHERE id = ?", (person_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Не найдено")
    return dict(row)


@app.post("/api/persons/import")
async def import_persons(file: UploadFile = File(...)):
    """Импорт карточек из JSON (seed.json)."""
    content = await file.read()
    persons = json.loads(content)
    if not isinstance(persons, list):
        raise HTTPException(400, "Ожидается массив JSON")

    conn = get_db()
    inserted = 0
    for p in persons:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO persons 
                (id, full_name, birth_year, death_year, region, district,
                 occupation, charge, arrest_date, sentence, sentence_date,
                 rehabilitation_date, biography, source, status)
                VALUES (:id, :full_name, :birth_year, :death_year, :region, :district,
                        :occupation, :charge, :arrest_date, :sentence, :sentence_date,
                        :rehabilitation_date, :biography, :source, :status)
            """, p)
            inserted += 1
        except Exception as e:
            print(f"Ошибка при вставке {p.get('full_name')}: {e}")
    conn.commit()
    conn.close()
    return {"imported": inserted}


@app.get("/api/stats")
async def stats():
    """Статистика по базе данных."""
    conn = get_db()
    persons_count = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    docs_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    regions = conn.execute(
        "SELECT region, COUNT(*) as cnt FROM persons GROUP BY region ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return {
        "persons": persons_count,
        "documents": docs_count,
        "chunks_in_db": chunks_count,
        "chunks_in_memory": len(VECTOR_STORE),
        "by_region": [dict(r) for r in regions],
    }