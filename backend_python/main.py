import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
import httpx

from database import init_db, SessionLocal, PersonCard, Document, DocumentChunk
from routers import auth_router, cards, rag


def _parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8501,http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


CPP_BACKEND_URL = os.getenv("CPP_BACKEND_URL", "http://cpp_backend:8080")

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


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/")
def root() -> dict:
    return {"service": "backend_python", "status": "ok"}


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
