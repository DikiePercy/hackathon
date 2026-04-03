import os
import json
import sqlite3
import httpx
import numpy as np
from typing import Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
import google.generativeai as genai

# ── Конфиг ──────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CPP_BACKEND_URL = os.getenv("CPP_BACKEND_URL", "http://localhost:8080")
DB_PATH = os.getenv("DB_PATH", "archive.db")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    llm = genai.GenerativeModel("gemini-2.0-flash")
else:
    llm = None

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(title="Голос из архива", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory vector store (будет заменён на ChromaDB) ─────────────────
VECTOR_STORE: list[dict] = []


# ── Утилиты для хеширования паролей ─────────────────────────────────────
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ── БД ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
                       CREATE TABLE IF NOT EXISTS users (
                                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                            username TEXT UNIQUE NOT NULL,
                                                            hashed_password TEXT NOT NULL,
                                                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                       );

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
                           person_id INTEGER REFERENCES persons(id),
                           chunk_text TEXT NOT NULL,
                           chunk_index INTEGER
                           );
                       """)
    conn.commit()
    conn.close()


# ── Auth helpers ────────────────────────────────────────────────────────
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception


# ── Helpers ──────────────────────────────────────────────────────────────
async def call_cpp_backend(text: str, chunk_size: int = 1000, overlap: int = 100) -> dict:
    """Отправляет текст в C++ backend, получает чанки."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:  # Увеличен timeout
            resp = await client.post(
                f"{CPP_BACKEND_URL}/process",
                json={"text": text, "chunk_size": chunk_size, "overlap": overlap}
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(500, f"C++ backend error: {str(e)}")


def get_embedding(text: str) -> np.ndarray:
    """Получает эмбеддинг через Gemini."""
    if not llm:
        # Заглушка для тестирования без API ключа
        return np.random.rand(768).astype(np.float32)

    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document"
    )
    return np.array(result["embedding"], dtype=np.float32)


def get_query_embedding(text: str) -> np.ndarray:
    """Эмбеддинг для поискового запроса."""
    if not llm:
        return np.random.rand(768).astype(np.float32)

    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_query"
    )
    return np.array(result["embedding"], dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def search_similar_chunks(query_embedding: np.ndarray, top_k: int = 5, person_id: Optional[int] = None) -> list[dict]:
    """Поиск похожих чанков по косинусному сходству."""
    if not VECTOR_STORE:
        return []

    # Фильтрация по person_id если указан
    filtered_store = VECTOR_STORE
    if person_id is not None:
        filtered_store = [item for item in VECTOR_STORE if item.get("person_id") == person_id]

    if not filtered_store:
        return []

    scores = [
        (cosine_similarity(query_embedding, item["embedding"]), item)
        for item in filtered_store
    ]
    scores.sort(key=lambda x: x[0], reverse=True)
    return [{"score": s, "text": item["text"], "person_id": item.get("person_id")} for s, item in scores[:top_k]]


# ── Startup ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    print("БД инициализирована")


# ── Auth Endpoints ───────────────────────────────────────────────────────

@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    """Регистрация нового пользователя."""
    conn = get_db()

    # Проверка существования пользователя
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Username already exists")

    # Создание пользователя
    hashed = get_password_hash(password)
    conn.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (username, hashed))
    conn.commit()
    conn.close()

    return {"message": "User created successfully"}


@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Вход пользователя и получение JWT токена."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (form_data.username,)).fetchone()
    conn.close()

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(400, "Incorrect username or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ── Health ──────────────────────────────────────────────────────────────

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


# ── Documents Endpoints ──────────────────────────────────────────────────

@app.post("/api/documents/upload")
async def upload_document(
        file: UploadFile = File(...),
        current_user: str = Depends(get_current_user)
):
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
        chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

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


@app.post("/upload_document")
async def upload_document_legacy(
        file: UploadFile = File(...),
        person_id: Optional[int] = Form(None),
        current_user: str = Depends(get_current_user)
):
    """
    Алиас для /api/documents/upload с поддержкой person_id.
    Frontend использует этот endpoint.
    """
    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    # Чанкинг через C++
    cpp_result = await call_cpp_backend(text)
    if cpp_result.get("is_garbage"):
        raise HTTPException(400, f"Документ отклонён: {cpp_result.get('reason')}")

    chunks: list[str] = cpp_result["chunks"]
    if not chunks:
        raise HTTPException(400, "Документ пуст после очистки")

    # Сохранение документа
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO documents (filename, content) VALUES (?, ?)",
        (file.filename, text)
    )
    doc_id = cur.lastrowid

    # Эмбеддинги + сохранение с person_id
    for i, chunk_text in enumerate(chunks):
        conn.execute(
            "INSERT INTO chunks (document_id, person_id, chunk_text, chunk_index) VALUES (?, ?, ?, ?)",
            (doc_id, person_id, chunk_text, i)
        )
        chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        embedding = get_embedding(chunk_text)
        VECTOR_STORE.append({
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "person_id": person_id,
            "filename": file.filename,
            "text": chunk_text,
            "embedding": embedding,
        })

    conn.commit()
    conn.close()

    return {
        "filename": file.filename,
        "chunks_created": len(chunks),
        "person_id": person_id,
    }


# ── Chat Endpoints ───────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    language: str = "auto"


class ChatRequest(BaseModel):
    query: str
    person_id: Optional[int] = None


@app.post("/api/ask")
async def ask(req: AskRequest, current_user: str = Depends(get_current_user)):
    """
    RAG-запрос:
    1. Эмбеддинг вопроса
    2. Поиск релевантных чанков
    3. Генерация ответа через Gemini
    """
    if not req.question.strip():
        raise HTTPException(400, "Вопрос не может быть пустым")

    query_emb = get_query_embedding(req.question)
    results = search_similar_chunks(query_emb, top_k=req.top_k)

    if not results:
        return {
            "answer": "Документы ещё не загружены. Сначала загрузите архивные документы через /upload_document",
            "sources": [],
        }

    context = "\n\n---\n\n".join(
        f"[Релевантность: {r['score']:.2f}]\n{r['text']}"
        for r in results
    )

    if llm:
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
    else:
        answer = f"[Тестовый режим] Найдено {len(results)} релевантных документов. Gemini API не настроен."

    return {
        "answer": answer,
        "sources": [
            {"score": r["score"], "excerpt": r["text"][:200] + "..."}
            for r in results
        ],
    }


@app.post("/chat")
async def chat(req: ChatRequest, current_user: str = Depends(get_current_user)):
    """
    Алиас для /api/ask, используется Frontend.
    """
    query_emb = get_query_embedding(req.query)
    results = search_similar_chunks(query_emb, top_k=5, person_id=req.person_id)

    if not results:
        return {
            "answer": "Документы не найдены.",
            "sources": [],
        }

    context = "\n\n".join(r["text"] for r in results)

    if llm:
        prompt = f"""Ты — архивный ассистент. Отвечай на основе документов.

ДОКУМЕНТЫ:
{context}

ВОПРОС: {req.query}

ОТВЕТ:"""
        response = llm.generate_content(prompt)
        answer = response.text
    else:
        answer = f"[Тестовый режим] Найдено {len(results)} документов."

    # Возвращаем person_id источников
    source_person_ids = list(set(r.get("person_id") for r in results if r.get("person_id")))

    return {
        "answer": answer,
        "sources": source_person_ids,
    }


# ── Persons/Cards Endpoints ──────────────────────────────────────────────

@app.get("/api/persons")
async def list_persons(
        region: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        current_user: str = Depends(get_current_user)
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


@app.get("/api/persons/alphabetical")
async def persons_alphabetical(current_user: str = Depends(get_current_user)):
    """
    Все репрессированные, сгруппированные по первой букве фамилии.
    Формат: {"А": [...], "Б": [...], ...}
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT id, full_name, birth_year, death_year,
                  occupation, region, sentence, rehabilitation_date
           FROM persons
           ORDER BY full_name"""
    ).fetchall()
    conn.close()

    index: dict[str, list] = {}
    for row in rows:
        d = dict(row)
        letter = d["full_name"][0].upper() if d["full_name"] else "?"
        index.setdefault(letter, []).append(d)

    return dict(sorted(index.items()))


@app.get("/api/persons/{person_id}")
async def get_person(person_id: int, current_user: str = Depends(get_current_user)):
    """Карточка конкретного репрессированного."""
    conn = get_db()
    row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Не найдено")
    return dict(row)


class CardCreate(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


@app.get("/cards")
async def get_cards(
        name: Optional[str] = None,
        category: Optional[str] = None,
        current_user: str = Depends(get_current_user)
):
    """
    Алиас для GET /api/persons.
    Маппинг: full_name → name, id → id, occupation → category.
    """
    conn = get_db()
    query = "SELECT id, full_name as name, occupation as category, biography as description, NULL as lat, NULL as lon FROM persons WHERE 1=1"
    params = []

    if name:
        query += " AND full_name LIKE ?"
        params.append(f"%{name}%")
    if category:
        query += " AND occupation LIKE ?"
        params.append(f"%{category}%")

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/cards")
async def create_card(card: CardCreate, current_user: str = Depends(get_current_user)):
    """
    Создание карточки person.
    Маппинг: name → full_name, category → occupation, description → biography.
    """
    conn = get_db()
    cur = conn.execute("""
                       INSERT INTO persons (full_name, occupation, biography)
                       VALUES (?, ?, ?)
                       """, (card.name, card.category, card.description))
    person_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"id": person_id, "name": card.name, "category": card.category}


@app.post("/api/persons/import")
async def import_persons(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
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
async def stats(current_user: str = Depends(get_current_user)):
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