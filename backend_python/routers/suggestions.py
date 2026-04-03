from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from database import PersonCard, PersonSuggestion, User, get_db

router = APIRouter()


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
    status: Optional[str] = None


class SuggestionResponse(BaseModel):
    id: int
    author_id: int
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
    status: Optional[str]
    created_at: datetime
    moderated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ModerationAction(BaseModel):
    comment: Optional[str] = None


def _validate_logic(data: SuggestionCreate) -> None:
    by = data.birth_year or 1900
    if by < 1800 or by > 2100:
        raise HTTPException(status_code=422, detail="birth_year is out of allowed range")
    if data.death_year is not None and data.death_year < by:
        raise HTTPException(status_code=422, detail="death_year must be >= birth_year")

    if data.sentence_date and data.arrest_date and data.sentence_date < data.arrest_date:
        raise HTTPException(status_code=422, detail="sentence_date must be after arrest_date")

    if data.rehabilitation_date and data.sentence_date and data.rehabilitation_date < data.sentence_date:
        raise HTTPException(status_code=422, detail="rehabilitation_date must be after sentence_date")


@router.post("/suggestions", response_model=SuggestionResponse, status_code=status.HTTP_201_CREATED)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_logic(payload)
    data = payload.model_dump()

    suggestion = PersonSuggestion(
        author_id=current_user.id,
        full_name=data["full_name"],
        birth_year=data.get("birth_year") or 1900,
        death_year=data.get("death_year"),
        nationality=data.get("nationality"),
        region=data.get("region") or "Unknown",
        district=data.get("district"),
        occupation=data.get("occupation"),
        charge=data.get("charge") or "Unknown",
        sentence=data.get("sentence"),
        arrest_date=data.get("arrest_date"),
        sentence_date=data.get("sentence_date"),
        rehabilitation_date=data.get("rehabilitation_date"),
        biography=data.get("biography") or "",
        source=data.get("source"),
        status=data.get("status"),
        state="pending",
    )

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

    return {"message": "Suggestion approved", "card_id": card.id, "suggestion_id": suggestion.id}


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
