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
    Date,
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy import inspect, text
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hackathon:hackathon@db:5432/hackathon")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user", server_default="user")
    
    chat_history = relationship("ChatHistory", back_populates="user")
    revisions = relationship("PersonRevision", back_populates="author")
    suggestions = relationship("PersonSuggestion", back_populates="author", foreign_keys="PersonSuggestion.author_id")


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
    nationality = Column(String, nullable=True)
    district = Column(String, nullable=True)
    charge = Column(Text, nullable=False)
    sentence = Column(Text, nullable=True)
    arrest_date = Column(Date, nullable=True)
    sentence_date = Column(Date, nullable=True)
    rehabilitation_date = Column(Date, nullable=True)
    status = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    source = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)
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


class PersonSuggestion(Base):
    __tablename__ = "person_suggestions"
    __table_args__ = (
        Index("ix_person_suggestions_state_created", "state", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_person_id = Column(Integer, ForeignKey("person_cards.id"), nullable=True, index=True)
    suggestion_kind = Column(String, nullable=False, default="create", server_default="create")

    full_name = Column(String, nullable=False, index=True)
    birth_year = Column(Integer, nullable=False, default=1900)
    death_year = Column(Integer, nullable=True)
    nationality = Column(String, nullable=True)
    region = Column(String, nullable=False, default="Unknown")
    district = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    charge = Column(Text, nullable=False, default="Unknown")
    sentence = Column(Text, nullable=True)
    arrest_date = Column(Date, nullable=True)
    sentence_date = Column(Date, nullable=True)
    rehabilitation_date = Column(Date, nullable=True)
    biography = Column(Text, nullable=False, default="")
    source = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)
    document_url = Column(Text, nullable=True)
    document_filename = Column(String, nullable=True)
    document_text = Column(Text, nullable=True)
    status = Column(String, nullable=True)

    state = Column(String, nullable=False, default="pending", server_default="pending")
    moderation_comment = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    moderated_at = Column(DateTime, nullable=True)
    moderated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    author = relationship("User", foreign_keys=[author_id], back_populates="suggestions")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations() -> None:
    """Best-effort additive migrations for already existing deployments."""
    inspector = inspect(engine)

    if inspector.has_table("users"):
        _ensure_column("users", "role", "VARCHAR", default="'user'")

    if inspector.has_table("person_cards"):
        _ensure_column("person_cards", "nationality", "VARCHAR")
        _ensure_column("person_cards", "district", "VARCHAR")
        _ensure_column("person_cards", "sentence", "TEXT")
        _ensure_column("person_cards", "arrest_date", "DATE")
        _ensure_column("person_cards", "sentence_date", "DATE")
        _ensure_column("person_cards", "rehabilitation_date", "DATE")
        _ensure_column("person_cards", "status", "VARCHAR")
        _ensure_column("person_cards", "photo_url", "TEXT")

    if inspector.has_table("person_suggestions"):
        _ensure_column("person_suggestions", "target_person_id", "INTEGER")
        _ensure_column("person_suggestions", "suggestion_kind", "VARCHAR", default="'create'")
        _ensure_column("person_suggestions", "photo_url", "TEXT")
        _ensure_column("person_suggestions", "document_url", "TEXT")
        _ensure_column("person_suggestions", "document_filename", "VARCHAR")
        _ensure_column("person_suggestions", "document_text", "TEXT")


def _ensure_column(table_name: str, column_name: str, sql_type: str, default: str | None = None) -> None:
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    if column_name in existing:
        return

    default_clause = f" DEFAULT {default}" if default is not None else ""
    statement = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}{default_clause}"
    with engine.begin() as conn:
        conn.execute(text(statement))
