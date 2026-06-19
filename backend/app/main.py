# -*- coding: utf-8 -*-
"""FastAPI app entry"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.database import engine, Base
from app.routers import pdf, questions, study, tags


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle"""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Smart Question Bank",
    description="FSRS spaced repetition learning system",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "uploads"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(pdf.router)
app.include_router(questions.router)
app.include_router(study.router)
app.include_router(tags.router)


@app.get("/")
def root():
    return {"message": "Smart Question Bank API", "docs": "/docs", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
