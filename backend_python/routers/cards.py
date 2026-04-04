import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, PersonCard, User, Document, DocumentChunk
from auth import get_current_user, require_admin
from rag_engine import add_documents_to_vector_db

router = APIRouter()


class PersonCardCreate(BaseModel):
    name: str
    birth_year: Optional[int] = 1900
    death_year: Optional[int] = None
    nationality: Optional[str] = None
    region: Optional[str] = "Unknown"
    district: Optional[str] = None
    category: Optional[str] = None
    charge: Optional[str] = "Unknown"
    sentence: Optional[str] = None
    arrest_date: Optional[date] = None
    sentence_date: Optional[date] = None
    rehabilitation_date: Optional[date] = None
    description: Optional[str] = ""
    source: Optional[str] = None
    photo_url: Optional[str] = None
    status: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class PersonCardResponse(BaseModel):
    id: int
    name: str
    birth_year: int
    death_year: Optional[int]
    nationality: Optional[str]
    region: str
    district: Optional[str]
    category: Optional[str]
    charge: str
    sentence: Optional[str]
    arrest_date: Optional[date]
    sentence_date: Optional[date]
    rehabilitation_date: Optional[date]
    description: str
    source: Optional[str]
    photo_url: Optional[str]
    status: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    
    class Config:
        from_attributes = True


class SeedPersonCard(BaseModel):
    id: Optional[int] = None
    full_name: str
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    nationality: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None
    occupation: Optional[str] = None
    charge: Optional[str] = None
    sentence: Optional[str] = None
    arrest_date: Optional[date] = None
    sentence_date: Optional[date] = None
    rehabilitation_date: Optional[date] = None
    biography: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None


def _normalize_card_payload(card_data: PersonCardCreate) -> dict:
    payload = card_data.model_dump()
    payload["birth_year"] = payload.get("birth_year") or 1900
    payload["region"] = payload.get("region") or "Unknown"
    payload["charge"] = payload.get("charge") or "Unknown"
    payload["description"] = payload.get("description") or ""
    return payload


def _import_seed_rows(items: List[SeedPersonCard], db: Session) -> dict:
    created = 0
    skipped_duplicates = 0
    seen_keys = set()

    for item in items:
        key = ((item.full_name or "").strip().lower(), item.birth_year or 1900)
        if key in seen_keys:
            skipped_duplicates += 1
            continue

        duplicate = db.query(PersonCard).filter(
            PersonCard.name.ilike(item.full_name),
            PersonCard.birth_year == (item.birth_year or 1900)
        ).first()
        if duplicate:
            skipped_duplicates += 1
            continue

        db.add(PersonCard(
            name=item.full_name,
            birth_year=item.birth_year or 1900,
            death_year=item.death_year,
            nationality=item.nationality,
            region=item.region or "Unknown",
            district=item.district,
            category=item.occupation,
            charge=item.charge or "Unknown",
            sentence=item.sentence,
            arrest_date=item.arrest_date,
            sentence_date=item.sentence_date,
            rehabilitation_date=item.rehabilitation_date,
            description=item.biography or "",
            source=item.source,
            status=item.status,
            lat=None,
            lon=None,
        ))
        seen_keys.add(key)
        created += 1

    return {
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "total": len(items),
    }


def import_bundled_seed_examples_into_db(db: Session) -> dict:
    root = Path(__file__).resolve().parents[2]
    candidate_files = [
        root / "asset" / "seed.json",
        root / "asset" / "test_data" / "seed.json",
    ]

    processed_files = []
    aggregate = {
        "created": 0,
        "skipped_duplicates": 0,
        "total": 0,
    }

    for seed_path in candidate_files:
        if not seed_path.exists():
            continue

        with seed_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, list):
            raise ValueError(f"Expected JSON array in {seed_path}")

        items = [SeedPersonCard(**item) for item in raw]
        result = _import_seed_rows(items, db)
        aggregate["created"] += result["created"]
        aggregate["skipped_duplicates"] += result["skipped_duplicates"]
        aggregate["total"] += result["total"]
        processed_files.append(str(seed_path.relative_to(root)))

    return {
        **aggregate,
        "files": processed_files,
    }


def _chunk_text_for_bootstrap(text: str, max_len: int = 1200) -> List[str]:
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    chunks: List[str] = []

    for block in blocks:
        if len(block) <= max_len:
            chunks.append(block)
            continue

        start = 0
        while start < len(block):
            end = min(len(block), start + max_len)
            chunks.append(block[start:end].strip())
            start = end

    return [c for c in chunks if c]


def _find_person_id_for_document(db: Session, filename: str, text: str) -> int | None:
    stem = Path(filename).stem.lower()
    rows = db.query(PersonCard.id, PersonCard.name).all()

    for row in rows:
        name = (row.name or "").lower().strip()
        if not name:
            continue
        parts = [p for p in name.replace("-", " ").split() if len(p) >= 3]
        if any(part in stem for part in parts):
            return row.id

    text_preview = text[:2000].lower()
    for row in rows:
        name = (row.name or "").lower().strip()
        if name and name in text_preview:
            return row.id

    return None


def import_bundled_documents_into_db(db: Session) -> dict:
    root = Path(__file__).resolve().parents[2]
    documents_dir = root / "asset" / "test_data" / "documents"
    if not documents_dir.exists():
        return {
            "created": 0,
            "skipped_duplicates": 0,
            "total": 0,
            "files": [],
        }

    files = sorted([p for p in documents_dir.glob("*.txt") if p.is_file()])
    created = 0
    skipped_duplicates = 0
    vector_failed = 0
    processed_files: List[str] = []

    for doc_path in files:
        rel_name = str(doc_path.relative_to(root))
        existing = db.query(Document).filter(Document.filename == rel_name).first()
        if existing:
            skipped_duplicates += 1
            continue

        content = doc_path.read_text(encoding="utf-8")
        document = Document(filename=rel_name, content=content)
        db.add(document)
        db.flush()

        person_id = _find_person_id_for_document(db, doc_path.name, content)
        chunks = _chunk_text_for_bootstrap(content)

        if chunks:
            try:
                add_documents_to_vector_db(chunks, person_id=person_id, document_name=doc_path.name)
            except Exception as exc:
                vector_failed += 1
                print(f"[bundled-docs] vector import skipped for {rel_name}: {exc}")
            for idx, chunk_text in enumerate(chunks):
                db.add(DocumentChunk(
                    document_id=document.id,
                    person_id=person_id,
                    chunk_text=chunk_text,
                    chunk_index=idx,
                ))

        created += 1
        processed_files.append(rel_name)

    return {
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "vector_failed": vector_failed,
        "total": len(files),
        "files": processed_files,
    }


def _to_public_person(card: PersonCard) -> dict:
    return {
        "id": card.id,
        "full_name": card.name,
        "birth_year": card.birth_year,
        "death_year": card.death_year,
        "nationality": card.nationality,
        "occupation": card.category,
        "arrest_date": card.arrest_date,
        "sentence": card.sentence or card.charge,
        "sentence_date": card.sentence_date,
        "rehabilitation_date": card.rehabilitation_date,
        "biography": card.description or card.content or "",
        "photo_url": card.photo_url or "https://via.placeholder.com/250x350.png?text=Archive",
        "documents": [],
    }


@router.get("/api/person/{person_id}")
def get_public_person(person_id: int, db: Session = Depends(get_db)) -> dict:
    card = db.query(PersonCard).filter(PersonCard.id == person_id).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    return _to_public_person(card)


@router.get("/api/persons/search")
def search_public_persons(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    term = q.strip()
    rows = (
        db.query(PersonCard)
        .filter(
            or_(
                PersonCard.name.ilike(f"%{term}%"),
                PersonCard.region.ilike(f"%{term}%"),
                PersonCard.category.ilike(f"%{term}%"),
                PersonCard.charge.ilike(f"%{term}%"),
            )
        )
        .order_by(PersonCard.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "full_name": row.name,
            "birth_year": row.birth_year,
            "death_year": row.death_year,
            "occupation": row.category,
        }
        for row in rows
    ]


@router.get("/api/persons")
def list_public_persons(
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(PersonCard)
    if q:
        term = q.strip()
        query = query.filter(
            or_(
                PersonCard.name.ilike(f"%{term}%"),
                PersonCard.region.ilike(f"%{term}%"),
                PersonCard.category.ilike(f"%{term}%"),
                PersonCard.charge.ilike(f"%{term}%"),
            )
        )

    rows = (
        query.order_by(PersonCard.name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "full_name": row.name,
            "birth_year": row.birth_year,
            "death_year": row.death_year,
            "nationality": row.nationality,
            "occupation": row.category,
            "region": row.region,
            "district": row.district,
            "charge": row.charge,
        }
        for row in rows
    ]


@router.get("/cards", response_model=List[PersonCardResponse])
def list_cards(
    name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    birth_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(PersonCard)
    
    if name:
        query = query.filter(PersonCard.name.ilike(f"%{name}%"))
    if category:
        query = query.filter(PersonCard.category.ilike(f"%{category}%"))
    if region:
        query = query.filter(PersonCard.region.ilike(f"%{region}%"))
    if birth_year is not None:
        query = query.filter(PersonCard.birth_year == birth_year)
    
    cards = query.all()
    return cards


@router.get("/cards/{card_id}", response_model=PersonCardResponse)
def get_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    card = db.query(PersonCard).filter(PersonCard.id == card_id).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    return card


@router.post("/cards", response_model=PersonCardResponse, status_code=status.HTTP_201_CREATED)
def create_card(
    card_data: PersonCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    payload = _normalize_card_payload(card_data)
    duplicate = db.query(PersonCard).filter(
        PersonCard.name.ilike(payload["name"]),
        PersonCard.birth_year == payload["birth_year"]
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate card: same name and birth year already exists"
        )

    new_card = PersonCard(**payload)
    db.add(new_card)
    db.commit()
    db.refresh(new_card)
    return new_card


@router.put("/cards/{card_id}", response_model=PersonCardResponse)
def update_card(
    card_id: int,
    card_data: PersonCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    payload = _normalize_card_payload(card_data)
    card = db.query(PersonCard).filter(PersonCard.id == card_id).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )

    duplicate = db.query(PersonCard).filter(
        PersonCard.id != card_id,
        PersonCard.name.ilike(payload["name"]),
        PersonCard.birth_year == payload["birth_year"]
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate card: same name and birth year already exists"
        )
    
    for key, value in payload.items():
        setattr(card, key, value)
    
    db.commit()
    db.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    card = db.query(PersonCard).filter(PersonCard.id == card_id).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    db.delete(card)
    db.commit()
    return None


@router.post("/cards/import")
def import_cards(
    cards_data: List[PersonCardCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    created = 0
    skipped_duplicates = 0
    seen_keys = set()

    for card_data in cards_data:
        payload = _normalize_card_payload(card_data)
        key = (payload["name"].strip().lower(), payload["birth_year"])
        if key in seen_keys:
            skipped_duplicates += 1
            continue

        duplicate = db.query(PersonCard).filter(
            PersonCard.name.ilike(payload["name"]),
            PersonCard.birth_year == payload["birth_year"]
        ).first()
        if duplicate:
            skipped_duplicates += 1
            continue

        db.add(PersonCard(**payload))
        seen_keys.add(key)
        created += 1

    db.commit()
    return {
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "total": len(cards_data)
    }


@router.post("/cards/import/seed")
def import_seed_cards(
    cards_data: List[SeedPersonCard],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = _import_seed_rows(cards_data, db)
    db.commit()
    return result


@router.post("/cards/import/seed/examples")
def import_seed_examples(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        result = import_bundled_seed_examples_into_db(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not result["files"]:
        raise HTTPException(status_code=404, detail="No bundled seed files found")

    db.commit()
    return result


@router.post("/api/persons/import")
async def import_persons_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    content = await file.read()
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="Expected JSON array")

    created = 0
    skipped_duplicates = 0
    seen_keys = set()

    for item in payload:
        seed = SeedPersonCard(**item)
        key = ((seed.full_name or "").strip().lower(), seed.birth_year or 1900)
        if key in seen_keys:
            skipped_duplicates += 1
            continue

        duplicate = db.query(PersonCard).filter(
            PersonCard.name.ilike(seed.full_name),
            PersonCard.birth_year == (seed.birth_year or 1900)
        ).first()
        if duplicate:
            skipped_duplicates += 1
            continue

        db.add(PersonCard(
            name=seed.full_name,
            birth_year=seed.birth_year or 1900,
            death_year=seed.death_year,
            nationality=seed.nationality,
            region=seed.region or "Unknown",
            district=seed.district,
            category=seed.occupation,
            charge=seed.charge or "Unknown",
            sentence=seed.sentence,
            arrest_date=seed.arrest_date,
            sentence_date=seed.sentence_date,
            rehabilitation_date=seed.rehabilitation_date,
            description=seed.biography or "",
            source=seed.source,
            status=seed.status,
            lat=None,
            lon=None,
        ))
        seen_keys.add(key)
        created += 1

    db.commit()
    return {"imported": created, "skipped_duplicates": skipped_duplicates, "total": len(payload)}


@router.get("/api/persons/alphabetical")
def persons_alphabetical(
    db: Session = Depends(get_db)
):
    rows = db.query(PersonCard).order_by(PersonCard.name.asc()).all()
    index = defaultdict(list)

    for card in rows:
        letter = (card.name[0].upper() if card.name else "?")
        index[letter].append({
            "id": card.id,
            "full_name": card.name,
            "birth_year": card.birth_year,
            "death_year": card.death_year,
            "occupation": card.category,
            "region": card.region,
            "sentence": None,
            "rehabilitation_date": None,
        })

    return dict(sorted(index.items()))
