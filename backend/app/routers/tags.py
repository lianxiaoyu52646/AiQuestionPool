# -*- coding: utf-8 -*-
"""Tag management routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Tag, Question
from app.schemas import TagCreate

router = APIRouter(prefix="/api/tags", tags=["Tags"])

# Default tags
DEFAULT_TAGS = [
    {"name": "Wrong", "color": "#EF4444"},
    {"name": "Important", "color": "#F59E0B"},
    {"name": "Mastered", "color": "#10B981"},
    {"name": "Confusing", "color": "#8B5CF6"},
    {"name": "HighFreq", "color": "#EC4899"},
]


@router.get("/list")
def list_tags(db: Session = Depends(get_db)):
    """Get all tags"""
    tags = db.query(Tag).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "color": t.color,
            "question_count": len(t.questions)
        }
        for t in tags
    ]


@router.post("/create")
def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
    """Create new tag"""
    existing = db.query(Tag).filter(Tag.name == tag.name).first()
    if existing:
        raise HTTPException(400, "Tag already exists")

    new_tag = Tag(name=tag.name, color=tag.color or "#3B82F6")
    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)

    return {"id": new_tag.id, "name": new_tag.name, "color": new_tag.color}


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Delete tag"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "Tag not found")

    db.delete(tag)
    db.commit()

    return {"message": "Tag deleted successfully"}


@router.post("/init-defaults")
def init_default_tags(db: Session = Depends(get_db)):
    """Initialize default tags"""
    created = []
    for tag_data in DEFAULT_TAGS:
        existing = db.query(Tag).filter(Tag.name == tag_data["name"]).first()
        if not existing:
            tag = Tag(name=tag_data["name"], color=tag_data["color"])
            db.add(tag)
            created.append(tag_data["name"])

    db.commit()
    return {"message": f"Created {len(created)} default tags", "tags": created}
