# -*- coding: utf-8 -*-
"""FastAPI app entry"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.database import engine, Base
from app.routers import pdf, questions, study, tags, exam


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
app.include_router(exam.router)

# --- 前端静态文件服务（生产模式）---
# vite build 输出到 backend/app/static/dist/
dist_dir = os.path.join(static_dir, "dist")
if os.path.isdir(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback: 所有非 /api、/static 路径返回 index.html"""
        # 排除 API 和静态文件路径
        if full_path.startswith(("api/", "static/")):
            raise HTTPException(404, "Not Found")
        index_path = os.path.join(dist_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        raise HTTPException(404, "Frontend not built. Run: cd frontend && npm run build")


@app.get("/")
def root():
    # 如果前端已构建，返回 index.html；否则返回 API 信息
    index_path = os.path.join(static_dir, "dist", "index.html")
    if os.path.isfile(index_path):
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
    return {"message": "Smart Question Bank API", "docs": "/docs", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
