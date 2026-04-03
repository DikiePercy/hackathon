import os
import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Must be set before importing auth/router modules.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("CHROMA_PATH", str(Path(__file__).resolve().parents[1] / ".chroma_test"))

BACKEND_PYTHON_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_PYTHON_DIR))

from database import Base, get_db  # noqa: E402
from routers import auth_router, cards, rag  # noqa: E402


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(cards.router)
    app.include_router(rag.router)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=test_engine)
