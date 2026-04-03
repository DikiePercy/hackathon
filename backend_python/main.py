from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import auth_router, cards, rag
import os

app = FastAPI(
    title="Archive Hackathon Backend",
    description="RAG-powered archive search with C++ text processing",
    version="1.0.0",
)


def _parse_cors_origins() -> list[str]:
    origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8501,http://localhost:3000")
    parsed = [origin.strip() for origin in origins.split(",") if origin.strip()]
    return parsed if parsed else ["http://localhost:8501"]


cors_origins = _parse_cors_origins()
allow_credentials = "*" not in cors_origins

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "python_backend"}

# Include routers
app.include_router(auth_router.router, tags=["auth"])
app.include_router(cards.router, tags=["cards"])
app.include_router(rag.router, tags=["rag"])


@app.on_event("startup")
def startup_event():
    secret_key = os.getenv("SECRET_KEY", "")
    if not secret_key or secret_key == "your-secret-key-change-in-production":
        raise RuntimeError("SECRET_KEY must be set to a non-default value")

    init_db()
    print("Database initialized")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
