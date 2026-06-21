# -*- coding: utf-8 -*-
"""App config"""
import os
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

# --- 路径计算（兼容 PyInstaller 打包）---
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后：exe 所在目录作为 BASE_DIR
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 开发模式：backend 目录（config.py 在 backend/app/ 下，两层 dirname 回到 backend/）
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 项目根目录（.env 所在位置）
PROJECT_ROOT = os.path.dirname(BASE_DIR)


class Settings(BaseSettings):
    """Settings"""
    model_config = SettingsConfigDict(
        protected_namespaces=(),
        env_file=os.path.join(PROJECT_ROOT, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # AI API 配置 — .env 不存在时使用默认值，题库/模考/学习功能不依赖 AI
    upstream_api_key: str = ""
    upstream_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    model_name: str = "glm-4"
    # 使用基于 backend 目录的绝对路径，避免受启动工作目录影响
    _db_path: str = os.path.join(BASE_DIR, "app", "static", "qa_database.db")
    _upload_path: str = os.path.join(BASE_DIR, "app", "static", "uploads")
    database_url: str = f"sqlite:///{_db_path}"
    upload_dir: str = _upload_path
    max_file_size: int = 52428800
    fsrs_w: list = [
        0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01,
        1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61
    ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
