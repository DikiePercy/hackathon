from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import httpx
import os
from database import get_db, User, ChatHistory, PersonCard, Document, DocumentChunk
from auth import get_current_user, require_admin
from rag_engine import add_documents_to_vector_db, answer_with_rag
import json

router = APIRouter()

CPP_BACKEND_URL = os.getenv("CPP_BACKEND_URL", "http://cpp_backend:8080")
CHAT_HISTORY_BACKEND = os.getenv("CHAT_HISTORY_BACKEND", "sql").strip().lower() or "sql"


class ChatRequest(BaseModel):
    query: str
    person_id: Optional[int] = None
    top_k: Optional[int] = 4


class ChatCitation(BaseModel):
    person_id: Optional[int] = None
    document_name: str
    chunk_index: Optional[int] = None
    score: Optional[float] = None
    quote: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[int]
    citations: List[ChatCitation]


def _save_chat_history_sql(db: Session, user_id: int, query: str, answer: str, person_ids: List[int]) -> None:
    chat_entry = ChatHistory(
        user_id=user_id,
        user_message=query,
        bot_response=answer,
        sources=json.dumps(person_ids),
    )
    db.add(chat_entry)
    db.commit()


def _save_chat_history(db: Session, user_id: int, query: str, answer: str, person_ids: List[int]) -> None:
    # Extension point: later add cloud history provider with same contract.
    if CHAT_HISTORY_BACKEND == "sql":
        _save_chat_history_sql(db, user_id, query, answer, person_ids)
        return
    raise RuntimeError(f"Unsupported CHAT_HISTORY_BACKEND: {CHAT_HISTORY_BACKEND}")


def _load_recent_history_sql(db: Session, user_id: int, limit: int = 6) -> List[dict]:
    entries = db.query(ChatHistory)\
        .filter(ChatHistory.user_id == user_id)\
        .order_by(ChatHistory.timestamp.desc())\
        .limit(max(1, limit))\
        .all()

    # Reverse to keep chronological order for better conversational continuity.
    entries = list(reversed(entries))
    return [
        {
            "user_message": e.user_message or "",
            "bot_response": e.bot_response or "",
        }
        for e in entries
    ]


def _load_recent_chat_history(db: Session, user_id: int, limit: int = 6) -> List[dict]:
    if CHAT_HISTORY_BACKEND == "sql":
        return _load_recent_history_sql(db, user_id, limit=limit)
    return []


@router.post("/upload_document")
async def upload_document(
    file: UploadFile = File(...),
    person_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required"
        )

    allowed_extensions = (".txt", ".md")
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt and .md files are supported"
        )

    # Check if person card exists
    card = db.query(PersonCard).filter(PersonCard.id == person_id).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person card not found"
        )
    
    # Read file content
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode file as UTF-8 text"
        )
    
    # Send to C++ backend for processing
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{CPP_BACKEND_URL}/process",
                json={"text": text}
            )
        response.raise_for_status()
        result = response.json()
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"C++ backend unavailable: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"C++ backend error: {str(e)}"
        )
    
    # Check if document is garbage
    if result.get("is_garbage", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document appears to be garbage or unreadable"
        )
    
    # Get chunks
    chunks = result.get("chunks", [])
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid content found in document"
        )
    
    # Persist source document in SQL for auditability and future extensions.
    document = Document(filename=file.filename, content=text)
    db.add(document)
    db.flush()

    # Add to vector database
    try:
        num_chunks = add_documents_to_vector_db(chunks, person_id, file.filename)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )

    for idx, chunk_text in enumerate(chunks):
        db.add(DocumentChunk(
            document_id=document.id,
            person_id=person_id,
            chunk_text=chunk_text,
            chunk_index=idx,
        ))

    db.commit()
    
    return {
        "message": "Document uploaded successfully",
        "document_id": document.id,
        "person_id": person_id,
        "chunks_created": num_chunks
    }


@router.post("/chat", response_model=ChatResponse)
def chat(
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = chat_request.query
    top_k = max(1, min(int(chat_request.top_k or 4), 8))
    recent_history = _load_recent_chat_history(db, current_user.id, limit=6)

    try:
        rag_result = answer_with_rag(
            query=query,
            top_k=top_k,
            candidate_k=max(10, top_k * 4),
            min_score=0.2,
            person_id=chat_request.person_id,
            chat_history=recent_history,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )

    answer = rag_result["answer"]
    person_ids = rag_result["sources"]
    citations = rag_result.get("citations", [])
    
    # Save to history via backend abstraction (sql now, cloud later).
    try:
        _save_chat_history(db, current_user.id, query, answer, person_ids)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    
    return ChatResponse(answer=answer, sources=person_ids, citations=citations)


@router.get("/chat/history")
def get_chat_history(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    if CHAT_HISTORY_BACKEND != "sql":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unsupported CHAT_HISTORY_BACKEND: {CHAT_HISTORY_BACKEND}"
        )

    total = db.query(func.count(ChatHistory.id))\
        .filter(ChatHistory.user_id == current_user.id)\
        .scalar() or 0

    history = db.query(ChatHistory)\
        .filter(ChatHistory.user_id == current_user.id)\
        .order_by(ChatHistory.timestamp.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()

    items = [
        {
            "id": entry.id,
            "user_message": entry.user_message,
            "bot_response": entry.bot_response,
            "timestamp": entry.timestamp,
            "sources": json.loads(entry.sources) if entry.sources else []
        }
        for entry in history
    ]

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total": int(total),
        "has_more": (offset + len(items)) < int(total),
        "storage_backend": CHAT_HISTORY_BACKEND,
    }
