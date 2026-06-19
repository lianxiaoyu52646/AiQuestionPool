# -*- coding: utf-8 -*-
"""Question routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Question, Category, Tag, question_tags, UserProgress
from app.services.fsrs_service import FSRSService
from app.schemas import QuestionUpdate, QuestionResponse, CategoryResponse

router = APIRouter(prefix="/api/questions", tags=["Questions"])
fsrs_service = FSRSService()


@router.get("/list")
def list_questions(
    category_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    search: Optional[str] = None,
    pdf_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get question list"""
    query = db.query(Question)

    if category_id:
        query = query.filter(Question.category_id == category_id)

    if tag_id:
        query = query.join(question_tags).filter(question_tags.c.tag_id == tag_id)

    if search:
        query = query.filter(Question.question_text.contains(search))

    if pdf_id:
        query = query.filter(Question.pdf_id == pdf_id)

    total = query.count()
    questions = query.offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": q.id,
                "question_text": q.question_text,
                "options": q.options,
                "answer": q.answer,
                "explanation": q.explanation,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "category": q.category.name if q.category else None,
                "page_number": q.page_number,
                "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in q.tags],
                "progress": {
                    "state": q.progress.state if q.progress else 0,
                    "due_date": q.progress.due_date.isoformat() if q.progress and q.progress.due_date else None,
                    "reps": q.progress.reps if q.progress else 0,
                    "stability": q.progress.stability if q.progress else 0,
                } if q.progress else None
            }
            for q in questions
        ]
    }


@router.get("/{question_id}")
def get_question(question_id: int, db: Session = Depends(get_db)):
    """Get single question details"""
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(404, "Question not found")

    return {
        "id": q.id,
        "question_text": q.question_text,
        "options": q.options,
        "answer": q.answer,
        "explanation": q.explanation,
        "question_type": q.question_type,
        "difficulty": q.difficulty,
        "category": q.category.name if q.category else None,
        "page_number": q.page_number,
        "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in q.tags],
        "pdf_id": q.pdf_id,
        "progress": {
            "state": q.progress.state if q.progress else 0,
            "due_date": q.progress.due_date.isoformat() if q.progress and q.progress.due_date else None,
            "reps": q.progress.reps if q.progress else 0,
            "lapses": q.progress.lapses if q.progress else 0,
        } if q.progress else None
    }


@router.put("/{question_id}")
def update_question(
    question_id: int,
    update: QuestionUpdate,
    db: Session = Depends(get_db)
):
    """Update question info"""
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(404, "Question not found")

    if update.question_text is not None:
        q.question_text = update.question_text
    if update.options is not None:
        q.options = update.options
    if update.answer is not None:
        q.answer = update.answer
    if update.explanation is not None:
        q.explanation = update.explanation
    if update.question_type is not None:
        q.question_type = update.question_type
    if update.difficulty is not None:
        q.difficulty = update.difficulty
    if update.category_id is not None:
        q.category_id = update.category_id

    db.commit()
    db.refresh(q)

    return {"message": "Updated successfully"}


@router.post("/{question_id}/tags/{tag_id}")
def add_tag_to_question(question_id: int, tag_id: int, db: Session = Depends(get_db)):
    """Add tag to question"""
    q = db.query(Question).filter(Question.id == question_id).first()
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not q or not tag:
        raise HTTPException(404, "Question or tag not found")

    if tag not in q.tags:
        q.tags.append(tag)
        db.commit()

    return {"message": "Tag added successfully"}


@router.delete("/{question_id}/tags/{tag_id}")
def remove_tag_from_question(question_id: int, tag_id: int, db: Session = Depends(get_db)):
    """Remove tag from question"""
    q = db.query(Question).filter(Question.id == question_id).first()
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not q or not tag:
        raise HTTPException(404, "Question or tag not found")

    if tag in q.tags:
        q.tags.remove(tag)
        db.commit()

    return {"message": "Tag removed successfully"}


@router.get("/categories/list")
def list_categories(db: Session = Depends(get_db)):
    """Get all categories"""
    categories = db.query(Category).order_by(Category.order_index).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "pdf_id": c.pdf_id,
            "order_index": c.order_index,
            "question_count": len(c.questions)
        }
        for c in categories
    ]
