import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from database import Document, DocumentChunk, PersonCard, PersonSuggestion, User, get_db
from rag_engine import add_documents_to_vector_db

router = APIRouter()

MAX_IMAGE_BYTES = 2 * 1024 * 1024  # < 2MB
MAX_DOCUMENT_BYTES = 3 * 1024 * 1024  # < 3MB
UPLOADS_ROOT = Path(os.getenv("UPLOADS_DIR", "/data/uploads"))
WEB_UPLOAD_PREFIX = "/uploads"


class SuggestionCreate(BaseModel):
    full_name: str
    birth_year: Optional[int] = 1900
    death_year: Optional[int] = None
    nationality: Optional[str] = None
    region: Optional[str] = "Unknown"
    district: Optional[str] = None
    occupation: Optional[str] = None
    charge: Optional[str] = "Unknown"
    sentence: Optional[str] = None
    arrest_date: Optional[date] = None
    sentence_date: Optional[date] = None
    rehabilitation_date: Optional[date] = None
    biography: Optional[str] = ""
    source: Optional[str] = None
    photo_url: Optional[str] = None
    document_url: Optional[str] = None
    document_filename: Optional[str] = None
    document_text: Optional[str] = None
    status: Optional[str] = None
    suggestion_kind: str = "create"
    target_person_id: Optional[int] = None


class SuggestionResponse(BaseModel):
    id: int
    author_id: int
    target_person_id: Optional[int]
    suggestion_kind: str
    state: str
    moderation_comment: Optional[str]
    full_name: str
    birth_year: int
    death_year: Optional[int]
    nationality: Optional[str]
    region: str
    district: Optional[str]
    occupation: Optional[str]
    charge: str
    sentence: Optional[str]
    arrest_date: Optional[date]
    sentence_date: Optional[date]
    rehabilitation_date: Optional[date]
    biography: str
    source: Optional[str]
    photo_url: Optional[str]
    document_url: Optional[str]
    document_filename: Optional[str]
    document_text: Optional[str]
    status: Optional[str]
    created_at: datetime
    moderated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ModerationAction(BaseModel):
    comment: Optional[str] = None


def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}") from exc


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid integer field") from exc


def _normalize_kind(kind: Optional[str]) -> str:
    value = (kind or "create").strip().lower()
    if value not in {"create", "update", "document"}:
        raise HTTPException(status_code=422, detail="suggestion_kind must be create, update or document")
    return value


def _validate_logic(data: SuggestionCreate, db: Session) -> None:
    by = data.birth_year or 1900
    if by < 1800 or by > 2100:
        raise HTTPException(status_code=422, detail="birth_year is out of allowed range")
    if data.death_year is not None and data.death_year < by:
        raise HTTPException(status_code=422, detail="death_year must be >= birth_year")

    if data.sentence_date and data.arrest_date and data.sentence_date < data.arrest_date:
        raise HTTPException(status_code=422, detail="sentence_date must be after arrest_date")

    if data.rehabilitation_date and data.sentence_date and data.rehabilitation_date < data.sentence_date:
        raise HTTPException(status_code=422, detail="rehabilitation_date must be after sentence_date")

    if data.suggestion_kind in {"update", "document"}:
        if not data.target_person_id:
            raise HTTPException(status_code=422, detail="target_person_id is required for update/document suggestions")
        exists = db.query(PersonCard).filter(PersonCard.id == data.target_person_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Target person not found")

    if data.suggestion_kind == "document":
        if not (data.document_text and data.document_text.strip()):
            raise HTTPException(status_code=422, detail="document_text or document file is required for document suggestions")


def _suggestion_from_payload(data: SuggestionCreate, current_user: User) -> PersonSuggestion:
    return PersonSuggestion(
        author_id=current_user.id,
        target_person_id=data.target_person_id,
        suggestion_kind=data.suggestion_kind,
        full_name=data.full_name,
        birth_year=data.birth_year or 1900,
        death_year=data.death_year,
        nationality=data.nationality,
        region=data.region or "Unknown",
        district=data.district,
        occupation=data.occupation,
        charge=data.charge or "Unknown",
        sentence=data.sentence,
        arrest_date=data.arrest_date,
        sentence_date=data.sentence_date,
        rehabilitation_date=data.rehabilitation_date,
        biography=data.biography or "",
        source=data.source,
        photo_url=data.photo_url,
        document_url=data.document_url,
        document_filename=data.document_filename,
        document_text=data.document_text,
        status=data.status,
        state="pending",
    )


async def _store_image(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Image filename is required")

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        raise HTTPException(status_code=400, detail="Unsupported image extension")

    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{ext}"
    target_path = UPLOADS_ROOT / filename

    total = 0
    with target_path.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total >= MAX_IMAGE_BYTES:
                out.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Image must be smaller than 2MB")
            out.write(chunk)

    return f"{WEB_UPLOAD_PREFIX}/{filename}"


async def _store_text_document(file: UploadFile) -> tuple[str, str, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Document filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".txt", ".md", ".markdown"}:
        raise HTTPException(status_code=400, detail="Only .txt and .md files are allowed")

    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="Document must be smaller than 3MB")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Unable to decode document as UTF-8") from exc

    if not text.strip():
        raise HTTPException(status_code=400, detail="Document is empty")

    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{ext}"
    target_path = UPLOADS_ROOT / filename
    target_path.write_bytes(data)

    return f"{WEB_UPLOAD_PREFIX}/{filename}", file.filename, text


def _split_into_chunks(text: str, chunk_size: int = 900) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []

    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(paragraph) <= chunk_size:
            current = paragraph
        else:
            for i in range(0, len(paragraph), chunk_size):
                chunks.append(paragraph[i:i + chunk_size])
            current = ""

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


@router.post("/suggestions", response_model=SuggestionResponse, status_code=status.HTTP_201_CREATED)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload.suggestion_kind = _normalize_kind(payload.suggestion_kind)
    _validate_logic(payload, db)
    suggestion = _suggestion_from_payload(payload, current_user)

    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.post("/suggestions/with-photo", response_model=SuggestionResponse, status_code=status.HTTP_201_CREATED)
async def create_suggestion_with_photo(
    full_name: str = Form(...),
    birth_year: Optional[str] = Form("1900"),
    death_year: Optional[str] = Form(None),
    nationality: Optional[str] = Form(None),
    region: Optional[str] = Form("Unknown"),
    district: Optional[str] = Form(None),
    occupation: Optional[str] = Form(None),
    charge: Optional[str] = Form("Unknown"),
    sentence: Optional[str] = Form(None),
    arrest_date: Optional[str] = Form(None),
    sentence_date: Optional[str] = Form(None),
    rehabilitation_date: Optional[str] = Form(None),
    biography: Optional[str] = Form(""),
    source: Optional[str] = Form(None),
    document_text_field: Optional[str] = Form(None, alias="document_text"),
    status_field: Optional[str] = Form(None, alias="status"),
    suggestion_kind: Optional[str] = Form("create"),
    target_person_id: Optional[str] = Form(None),
    photo: UploadFile | None = File(None),
    document_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    photo_url = None
    document_url = None
    document_filename = None
    document_text = (document_text_field or "").strip() or None

    if photo is not None:
        photo_url = await _store_image(photo)

    if document_file is not None:
        doc_url, doc_name, doc_text = await _store_text_document(document_file)
        document_url = doc_url
        document_filename = doc_name
        if document_text:
            document_text = f"{document_text}\n\n{doc_text}".strip()
        else:
            document_text = doc_text

    payload = SuggestionCreate(
        full_name=full_name,
        birth_year=_parse_int(birth_year) or 1900,
        death_year=_parse_int(death_year),
        nationality=(nationality or None),
        region=(region or "Unknown"),
        district=(district or None),
        occupation=(occupation or None),
        charge=(charge or "Unknown"),
        sentence=(sentence or None),
        arrest_date=_parse_date(arrest_date, "arrest_date"),
        sentence_date=_parse_date(sentence_date, "sentence_date"),
        rehabilitation_date=_parse_date(rehabilitation_date, "rehabilitation_date"),
        biography=(biography or ""),
        source=(source or None),
        photo_url=photo_url,
        document_url=document_url,
        document_filename=document_filename,
        document_text=document_text,
        status=(status_field or None),
        suggestion_kind=_normalize_kind(suggestion_kind),
        target_person_id=_parse_int(target_person_id),
    )

    _validate_logic(payload, db)
    suggestion = _suggestion_from_payload(payload, current_user)
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.get("/suggestions/my", response_model=list[SuggestionResponse])
def my_suggestions(
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(PersonSuggestion)
        .filter(PersonSuggestion.author_id == current_user.id)
        .order_by(PersonSuggestion.created_at.desc())
        .limit(limit)
        .all()
    )
    return rows


@router.get("/admin/suggestions", response_model=list[SuggestionResponse])
def list_suggestions_admin(
    state: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(PersonSuggestion)
    if state:
        query = query.filter(PersonSuggestion.state == state)

    return query.order_by(PersonSuggestion.created_at.desc()).limit(limit).all()


@router.post("/admin/suggestions/{suggestion_id}/approve")
def approve_suggestion(
    suggestion_id: int,
    action: ModerationAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    suggestion = db.query(PersonSuggestion).filter(PersonSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.state != "pending":
        raise HTTPException(status_code=400, detail="Only pending suggestions can be approved")

    if suggestion.suggestion_kind == "update":
        if not suggestion.target_person_id:
            raise HTTPException(status_code=422, detail="target_person_id missing for update suggestion")
        card = db.query(PersonCard).filter(PersonCard.id == suggestion.target_person_id).first()
        if not card:
            raise HTTPException(status_code=404, detail="Target person not found")

        duplicate = db.query(PersonCard).filter(
            PersonCard.id != card.id,
            PersonCard.name.ilike(suggestion.full_name),
            PersonCard.birth_year == suggestion.birth_year,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Another card with same name and birth_year already exists")

        card.name = suggestion.full_name
        card.birth_year = suggestion.birth_year
        card.death_year = suggestion.death_year
        card.nationality = suggestion.nationality
        card.region = suggestion.region
        card.district = suggestion.district
        card.category = suggestion.occupation
        card.charge = suggestion.charge
        card.sentence = suggestion.sentence
        card.arrest_date = suggestion.arrest_date
        card.sentence_date = suggestion.sentence_date
        card.rehabilitation_date = suggestion.rehabilitation_date
        card.description = suggestion.biography
        card.source = suggestion.source
        card.photo_url = suggestion.photo_url or card.photo_url
        card.status = suggestion.status
        card.content = suggestion.biography or card.content or ""
    elif suggestion.suggestion_kind == "document":
        if not suggestion.target_person_id:
            raise HTTPException(status_code=422, detail="target_person_id missing for document suggestion")
        card = db.query(PersonCard).filter(PersonCard.id == suggestion.target_person_id).first()
        if not card:
            raise HTTPException(status_code=404, detail="Target person not found")

        if not (suggestion.document_text and suggestion.document_text.strip()):
            raise HTTPException(status_code=422, detail="document_text is required for document suggestion")

        doc_filename = suggestion.document_filename or f"suggestion_{suggestion.id}.md"
        document = Document(filename=doc_filename, content=suggestion.document_text)
        db.add(document)
        db.flush()

        chunks = _split_into_chunks(suggestion.document_text)
        if not chunks:
            chunks = [suggestion.document_text]

        for i, chunk in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    person_id=card.id,
                    chunk_text=chunk,
                    chunk_index=i,
                )
            )

        try:
            add_documents_to_vector_db(chunks, person_id=card.id, document_name=doc_filename)
        except Exception:
            # Keep DB-linked document even if vector DB is temporarily unavailable.
            pass
    else:
        duplicate = db.query(PersonCard).filter(
            PersonCard.name.ilike(suggestion.full_name),
            PersonCard.birth_year == suggestion.birth_year,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Duplicate card already exists")

        card = PersonCard(
            name=suggestion.full_name,
            birth_year=suggestion.birth_year,
            death_year=suggestion.death_year,
            nationality=suggestion.nationality,
            region=suggestion.region,
            district=suggestion.district,
            category=suggestion.occupation,
            charge=suggestion.charge,
            sentence=suggestion.sentence,
            arrest_date=suggestion.arrest_date,
            sentence_date=suggestion.sentence_date,
            rehabilitation_date=suggestion.rehabilitation_date,
            description=suggestion.biography,
            source=suggestion.source,
            photo_url=suggestion.photo_url,
            status=suggestion.status,
            lat=None,
            lon=None,
            content=suggestion.biography or "",
        )
        db.add(card)

    suggestion.state = "approved"
    suggestion.moderation_comment = action.comment
    suggestion.moderated_at = datetime.utcnow()
    suggestion.moderated_by = current_user.id

    db.commit()
    db.refresh(card)

    return {
        "message": "Suggestion approved",
        "card_id": card.id,
        "suggestion_id": suggestion.id,
        "kind": suggestion.suggestion_kind,
    }


@router.post("/admin/suggestions/{suggestion_id}/reject")
def reject_suggestion(
    suggestion_id: int,
    action: ModerationAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    suggestion = db.query(PersonSuggestion).filter(PersonSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.state != "pending":
        raise HTTPException(status_code=400, detail="Only pending suggestions can be rejected")

    suggestion.state = "rejected"
    suggestion.moderation_comment = action.comment
    suggestion.moderated_at = datetime.utcnow()
    suggestion.moderated_by = current_user.id
    db.commit()
    return {"message": "Suggestion rejected", "suggestion_id": suggestion.id}


@router.delete("/admin/suggestions/{suggestion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suggestion_admin(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    suggestion = db.query(PersonSuggestion).filter(PersonSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    db.delete(suggestion)
    db.commit()
    return None
