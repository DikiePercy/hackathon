from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hackathon:hackathon@db:5432/hackathon")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    
    chat_history = relationship("ChatHistory", back_populates="user")


class PersonCard(Base):
    __tablename__ = "person_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    birth_year = Column(Integer, nullable=False, index=True)
    death_year = Column(Integer, nullable=True)
    region = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=True)
    charge = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    source = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)


class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    sources = Column(String, nullable=True)  # JSON array of person_ids
    
    user = relationship("User", back_populates="chat_history")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Keep existing local DBs usable without a full migration stack.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE person_cards ADD COLUMN IF NOT EXISTS birth_year INTEGER"))
        conn.execute(text("ALTER TABLE person_cards ADD COLUMN IF NOT EXISTS death_year INTEGER"))
        conn.execute(text("ALTER TABLE person_cards ADD COLUMN IF NOT EXISTS region VARCHAR"))
        conn.execute(text("ALTER TABLE person_cards ADD COLUMN IF NOT EXISTS charge TEXT"))
        conn.execute(text("ALTER TABLE person_cards ADD COLUMN IF NOT EXISTS source TEXT"))
        conn.execute(text("UPDATE person_cards SET birth_year = 1900 WHERE birth_year IS NULL"))
        conn.execute(text("UPDATE person_cards SET region = 'Unknown' WHERE region IS NULL"))
        conn.execute(text("UPDATE person_cards SET charge = 'Unknown' WHERE charge IS NULL"))
        conn.execute(text("UPDATE person_cards SET description = '' WHERE description IS NULL"))
