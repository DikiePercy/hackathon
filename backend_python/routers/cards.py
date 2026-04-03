from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, PersonCard, User
from auth import get_current_user

router = APIRouter()


class PersonCardCreate(BaseModel):
    name: str
    birth_year: int
    death_year: Optional[int] = None
    region: str
    category: Optional[str] = None
    charge: str
    description: str
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
    full_name: str
    birth_year: int
    death_year: Optional[int] = None
    region: str
    occupation: Optional[str] = None
    charge: str
    biography: str
    source: Optional[str] = None


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
    duplicate = db.query(PersonCard).filter(
        PersonCard.name.ilike(card_data.name),
        PersonCard.birth_year == card_data.birth_year
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate card: same name and birth year already exists"
        )

    new_card = PersonCard(**card_data.model_dump())
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
    card = db.query(PersonCard).filter(PersonCard.id == card_id).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )

    duplicate = db.query(PersonCard).filter(
        PersonCard.id != card_id,
        PersonCard.name.ilike(card_data.name),
        PersonCard.birth_year == card_data.birth_year
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate card: same name and birth year already exists"
        )
    
    for key, value in card_data.model_dump().items():
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
        key = (card_data.name.strip().lower(), card_data.birth_year)
        if key in seen_keys:
            skipped_duplicates += 1
            continue

        duplicate = db.query(PersonCard).filter(
            PersonCard.name.ilike(card_data.name),
            PersonCard.birth_year == card_data.birth_year
        ).first()
        if duplicate:
            skipped_duplicates += 1
            continue

        db.add(PersonCard(**card_data.model_dump()))
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
