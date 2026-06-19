# -*- coding: utf-8 -*-
"""Pydantic data models"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class QuestionUpdate(BaseModel):
    """Question update request"""
    question_text: Optional[str] = None
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[int] = None
    category_id: Optional[int] = None


class QuestionResponse(BaseModel):
    """Question response"""
    id: int
    question_text: str
    options: List[str]
    answer: str
    explanation: str
    question_type: str
    difficulty: int
    category: Optional[str] = None
    page_number: int
    tags: List[dict] = []

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    """Category response"""
    id: int
    name: str
    pdf_id: int
    order_index: int
    question_count: int = 0

    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    """Tag creation request"""
    name: str
    color: str = "#3B82F6"


class TagResponse(BaseModel):
    """Tag response"""
    id: int
    name: str
    color: str
    question_count: int = 0

    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    """Review submission request - auto-rated by system"""
    question_id: int
    selected_answer: str  # User's selected answer (e.g. "A", "AB", "True", or text)
    used_time_sec: int = 0  # Time spent on this question in seconds
    is_practice: bool = False  # If True, only log + tag, skip FSRS scheduling
