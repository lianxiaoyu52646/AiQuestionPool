# -*- coding: utf-8 -*-
"""App config"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    """Settings"""
    model_config = SettingsConfigDict(
        protected_namespaces=(),
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8"
    )
    
    upstream_api_key: str
    upstream_base_url: str
    model_name: str = "/model"
    database_url: str = "sqlite:///./app/static/qa_database.db"
    upload_dir: str = "./app/static/uploads"
    max_file_size: int = 52428800
    fsrs_w: list = [
        0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01,
        1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61
    ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
