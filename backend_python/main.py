from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import auth_router, cards, rag

app = FastAPI(
    title="Archive Hackathon Backend",
    description="RAG-powered archive search with C++ text processing",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    init_db()
    print("Database initialized")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
