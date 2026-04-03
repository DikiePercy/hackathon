from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://archive:archive@db:5432/archive")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    
    chat_history = relationship("ChatHistory", back_populates="user")
    revisions = relationship("PersonRevision", back_populates="author")


class PersonCard(Base):
    __tablename__ = "person_cards"
    __table_args__ = (
        UniqueConstraint("name", "birth_year", name="uq_person_cards_name_birth_year"),
        Index("ix_person_cards_name_region", "name", "region"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False, default="")
    birth_year = Column(Integer, nullable=False, index=True)
    death_year = Column(Integer, nullable=True)
    region = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=True)
    charge = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    source = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    revisions = relationship("PersonRevision", back_populates="person", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="person")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document_chunk_index", "document_id", "chunk_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("person_cards.id"), nullable=True, index=True)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")
    person = relationship("PersonCard", back_populates="chunks")


class PersonRevision(Base):
    __tablename__ = "person_revisions"
    __table_args__ = (
        Index("ix_person_revisions_person_created_at", "person_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    comment = Column(String, nullable=True)
    snapshot = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    person = relationship("PersonCard", back_populates="revisions")
    author = relationship("User", back_populates="revisions")


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
