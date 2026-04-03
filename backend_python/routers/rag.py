from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import httpx
import os
from database import get_db, User, ChatHistory, PersonCard, Document, DocumentChunk
from auth import get_current_user
from rag_engine import add_documents_to_vector_db, answer_with_rag
import json

router = APIRouter()

CPP_BACKEND_URL = os.getenv("CPP_BACKEND_URL", "http://cpp_backend:8080")


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[int]


@router.post("/upload_document")
async def upload_document(
    file: UploadFile = File(...),
    person_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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

    try:
        rag_result = answer_with_rag(query, top_k=3)
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
    
    # Save to chat history
    chat_entry = ChatHistory(
        user_id=current_user.id,
        user_message=query,
        bot_response=answer,
        sources=json.dumps(person_ids)
    )
    db.add(chat_entry)
    db.commit()
    
    return ChatResponse(answer=answer, sources=person_ids)


@router.get("/chat/history")
def get_chat_history(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    history = db.query(ChatHistory)\
        .filter(ChatHistory.user_id == current_user.id)\
        .order_by(ChatHistory.timestamp.desc())\
        .limit(limit)\
        .all()
    
    return [
        {
            "id": entry.id,
            "user_message": entry.user_message,
            "bot_response": entry.bot_response,
            "timestamp": entry.timestamp,
            "sources": json.loads(entry.sources) if entry.sources else []
        }
        for entry in history
    ]
