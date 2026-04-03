from fastapi import FastAPI

from app.routers import api_router

app = FastAPI(
    title="Hackathon Backend",
    description="Basic FastAPI backend starter",
    version="0.1.0",
)

app.include_router(api_router)
