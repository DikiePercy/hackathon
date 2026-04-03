import os

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, User
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    SESSION_COOKIE_NAME,
    COOKIE_SECURE,
)

router = APIRouter()


class UserRegister(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserPublic(BaseModel):
    id: int
    username: str
    role: str


def _validate_password_strength(password: str) -> None:
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must contain at least 6 characters")
    has_upper = any(ch.isupper() for ch in password)
    has_lower = any(ch.islower() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    if not ((has_upper and has_lower and has_digit) or (has_lower and has_digit)):
        raise HTTPException(
            status_code=400,
            detail="Password must include letters and digits",
        )


def ensure_admin_user(db: Session) -> None:
    admin_username = os.getenv("ADMIN_USERNAME", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not admin_username or not admin_password:
        return

    admin = db.query(User).filter(User.username == admin_username).first()
    if admin:
        if admin.role != "admin":
            admin.role = "admin"
            db.commit()
        return

    db.add(
        User(
            username=admin_username,
            password_hash=get_password_hash(admin_password),
            role="admin",
        )
    )
    db.commit()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    _validate_password_strength(user_data.password)
    # Check if user exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, password_hash=hashed_password, role="user")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User registered successfully", "username": new_user.username}


@router.post("/login", response_model=Token)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Find user
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user.username, "role": user.role})

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 2,
        path="/",
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return UserPublic(id=current_user.id, username=current_user.username, role=current_user.role)
