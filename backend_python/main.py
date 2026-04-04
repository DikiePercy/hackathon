import os
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
import httpx

from database import init_db, SessionLocal, PersonCard, Document, DocumentChunk, get_db, User
from auth import require_admin
from routers import auth_router, cards, rag, suggestions
from rag_engine import add_documents_to_vector_db, get_runtime_config, update_runtime_config


def _parse_cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:8501,http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500,http://localhost:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


CPP_BACKEND_URL = os.getenv("CPP_BACKEND_URL", "http://cpp_backend:8080")
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/data/uploads"))

app = FastAPI(title="Golos iz Arkhiva API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(cards.router)
app.include_router(rag.router)
app.include_router(suggestions.router)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


class AIRuntimeConfigPatch(BaseModel):
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    rag_llm_provider: str | None = None
    rag_embedding_provider: str | None = None
    rag_gemini_model: str | None = None
    rag_claude_model: str | None = None
    rag_gemini_embedding_model: str | None = None
    rag_openai_embedding_model: str | None = None


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    db = SessionLocal()
    try:
        auth_router.ensure_admin_user(db)

        auto_seed = os.getenv("AUTO_IMPORT_BUNDLED_SEEDS", "true").strip().lower() in {"1", "true", "yes"}
        if auto_seed:
            try:
                seed_result = cards.import_bundled_seed_examples_into_db(db)
                if seed_result.get("files"):
                    db.commit()
            except Exception as exc:
                db.rollback()
                print(f"[startup] bundled seed auto-import skipped: {exc}")

        auto_docs = os.getenv("AUTO_IMPORT_BUNDLED_DOCUMENTS", "true").strip().lower() in {"1", "true", "yes"}
        if auto_docs:
            try:
                docs_result = cards.import_bundled_documents_into_db(db)
                if docs_result.get("files"):
                    db.commit()
            except Exception as exc:
                db.rollback()
                print(f"[startup] bundled documents auto-import skipped: {exc}")
    finally:
        db.close()


@app.get("/")
def root() -> dict:
    return {"service": "backend_python", "status": "ok"}


@app.get("/admin/ai/runtime-config")
def admin_get_ai_runtime_config(current_user: User = Depends(require_admin)) -> dict:
    return {
        "config": get_runtime_config(mask_secrets=True),
        "allowed_llm_providers": ["gemini", "claude"],
        "allowed_embedding_providers": ["gemini", "openai"],
    }


@app.post("/admin/ai/runtime-config")
def admin_update_ai_runtime_config(
    payload: AIRuntimeConfigPatch,
    current_user: User = Depends(require_admin),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)

    if "rag_llm_provider" in updates:
        updates["rag_llm_provider"] = (updates["rag_llm_provider"] or "").strip().lower()
        if updates["rag_llm_provider"] not in {"gemini", "claude"}:
            raise HTTPException(status_code=400, detail="rag_llm_provider must be one of: gemini, claude")

    if "rag_embedding_provider" in updates:
        updates["rag_embedding_provider"] = (updates["rag_embedding_provider"] or "").strip().lower()
        if updates["rag_embedding_provider"] not in {"gemini", "openai"}:
            raise HTTPException(status_code=400, detail="rag_embedding_provider must be one of: gemini, openai")

    effective = update_runtime_config(updates)
    return {"message": "AI runtime config updated", "config": effective}


@app.get("/health")
async def health() -> dict:
    cpp_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{CPP_BACKEND_URL}/health")
            cpp_ok = response.status_code == 200
    except Exception:
        cpp_ok = False

    db: Session = SessionLocal()
    try:
        persons = db.query(func.count(PersonCard.id)).scalar() or 0
        documents = db.query(func.count(Document.id)).scalar() or 0
        chunks = db.query(func.count(DocumentChunk.id)).scalar() or 0
    finally:
        db.close()

    return {
        "status": "ok",
        "cpp_backend": "ok" if cpp_ok else "unavailable",
        "persons": persons,
        "documents": documents,
        "chunks": chunks,
    }


@app.get("/api/stats")
def stats() -> dict:
    db: Session = SessionLocal()
    try:
        persons_count = db.query(func.count(PersonCard.id)).scalar() or 0
        docs_count = db.query(func.count(Document.id)).scalar() or 0
        chunks_count = db.query(func.count(DocumentChunk.id)).scalar() or 0

        by_region_rows = (
            db.query(PersonCard.region, func.count(PersonCard.id))
            .group_by(PersonCard.region)
            .order_by(func.count(PersonCard.id).desc())
            .all()
        )
    finally:
        db.close()

    return {
        "persons": persons_count,
        "documents": docs_count,
        "chunks_in_db": chunks_count,
        "by_region": [
            {"region": row[0] or "Unknown", "cnt": row[1]}
            for row in by_region_rows
        ],
    }


@app.post("/cards/upload", status_code=status.HTTP_201_CREATED)
async def upload_card_with_document(
    name: str = Form(...),
    category: str = Form("Unknown"),
    birth_year: int = Form(1900),
    death_year: int | None = Form(None),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    if not file.filename.lower().endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported")

    file_bytes = await file.read()
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Unable to decode file as UTF-8") from exc

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            cpp_response = await client.post(f"{CPP_BACKEND_URL}/process", json={"text": text})
        cpp_response.raise_for_status()
        cpp_payload = cpp_response.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"C++ backend unavailable: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=503, detail=f"C++ backend error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Invalid JSON from C++ backend") from exc

    if cpp_payload.get("is_garbage", True):
        raise HTTPException(status_code=400, detail="Uploaded text is detected as garbage")

    chunks = cpp_payload.get("chunks", [])
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks produced from document")

    db: Session = SessionLocal()
    try:
        card = PersonCard(
            name=name,
            category=category,
            content=text,
            birth_year=birth_year,
            death_year=death_year,
            lat=lat,
            lon=lon,
            region="Unknown",
            charge="Unknown",
            description=text[:2000],
        )
        db.add(card)
        db.flush()

        document = Document(filename=file.filename, content=text)
        db.add(document)
        db.flush()

        try:
            add_documents_to_vector_db(chunks, person_id=card.id, document_name=file.filename)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail=f"RAG vector store error: {exc}") from exc

        for i, chunk in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    person_id=card.id,
                    chunk_text=chunk,
                    chunk_index=i,
                )
            )

        db.commit()
        db.refresh(card)
    finally:
        db.close()

    return {
        "id": card.id,
        "name": card.name,
        "category": card.category,
        "birth_year": card.birth_year,
        "death_year": card.death_year,
        "lat": card.lat,
        "lon": card.lon,
        "is_garbage": False,
        "chunks_count": len(chunks),
    }


@app.get("/cards/grouped")
def cards_grouped(db: Session = Depends(get_db)) -> dict:
    cards_rows = db.query(PersonCard).order_by(func.lower(PersonCard.name)).all()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for card in cards_rows:
        first_char = card.name[0].upper() if card.name else "#"
        grouped[first_char].append(
            {
                "id": card.id,
                "name": card.name,
                "category": card.category,
                "content": card.content,
                "birth_year": card.birth_year,
                "death_year": card.death_year,
                "lat": card.lat,
                "lon": card.lon,
            }
        )

    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))
