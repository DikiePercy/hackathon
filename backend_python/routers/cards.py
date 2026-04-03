import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, PersonCard, User
from auth import get_current_user

router = APIRouter()


class PersonCardCreate(BaseModel):
    name: str
    birth_year: Optional[int] = 1900
    death_year: Optional[int] = None
    region: Optional[str] = "Unknown"
    category: Optional[str] = None
    charge: Optional[str] = "Unknown"
    description: Optional[str] = ""
    source: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class PersonCardResponse(BaseModel):
    id: int
    name: str
    birth_year: int
    death_year: Optional[int]
    region: str
    category: Optional[str]
    charge: str
    description: str
    source: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    
    class Config:
        from_attributes = True


class SeedPersonCard(BaseModel):
    id: Optional[int] = None
    full_name: str
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    region: Optional[str] = None
    occupation: Optional[str] = None
    charge: Optional[str] = None
    biography: Optional[str] = None
    source: Optional[str] = None


def _normalize_card_payload(card_data: PersonCardCreate) -> dict:
    payload = card_data.model_dump()
    payload["birth_year"] = payload.get("birth_year") or 1900
    payload["region"] = payload.get("region") or "Unknown"
    payload["charge"] = payload.get("charge") or "Unknown"
    payload["description"] = payload.get("description") or ""
    return payload


def _to_public_person(card: PersonCard) -> dict:
    return {
        "id": card.id,
        "full_name": card.name,
        "birth_year": card.birth_year,
        "death_year": card.death_year,
        "nationality": None,
        "occupation": card.category,
        "arrest_date": None,
        "sentence": card.charge,
        "sentence_date": None,
        "rehabilitation_date": None,
        "biography": card.description or card.content or "",
        "photo_url": "https://via.placeholder.com/250x350.png?text=Portrait",
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
    rows = (
        db.query(PersonCard)
        .filter(PersonCard.name.ilike(f"%{q}%"))
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
    created = 0
    skipped_duplicates = 0
    seen_keys = set()

    for item in cards_data:
        key = (item.full_name.strip().lower(), item.birth_year)
        if key in seen_keys:
            skipped_duplicates += 1
            continue

        duplicate = db.query(PersonCard).filter(
            PersonCard.name.ilike(item.full_name),
            PersonCard.birth_year == item.birth_year
        ).first()
        if duplicate:
            skipped_duplicates += 1
            continue

        db.add(PersonCard(
            name=item.full_name,
            birth_year=item.birth_year,
            death_year=item.death_year,
            region=item.region,
            category=item.occupation,
            charge=item.charge,
            description=item.biography,
            source=item.source,
            lat=None,
            lon=None,
        ))
        seen_keys.add(key)
        created += 1

    db.commit()
    return {
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "total": len(cards_data)
    }


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
            region=seed.region or "Unknown",
            category=seed.occupation,
            charge=seed.charge or "Unknown",
            description=seed.biography or "",
            source=seed.source,
            lat=None,
            lon=None,
        ))
        seen_keys.add(key)
        created += 1

    db.commit()
    return {"imported": created, "skipped_duplicates": skipped_duplicates, "total": len(payload)}


@router.get("/api/persons/alphabetical")
def persons_alphabetical(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
