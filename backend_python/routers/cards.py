from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, PersonCard, User
from auth import get_current_user

router = APIRouter()


class PersonCardCreate(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class PersonCardResponse(BaseModel):
    id: int
    name: str
    category: str
    description: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    
    class Config:
        from_attributes = True


@router.get("/cards", response_model=List[PersonCardResponse])
def list_cards(
    name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(PersonCard)
    
    if name:
        query = query.filter(PersonCard.name.ilike(f"%{name}%"))
    if category:
        query = query.filter(PersonCard.category.ilike(f"%{category}%"))
    
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
