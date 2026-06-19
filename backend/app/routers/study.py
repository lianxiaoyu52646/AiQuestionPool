# -*- coding: utf-8 -*-
"""Study and review routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Question, UserProgress, ReviewLog, question_tags, Category
from app.services.fsrs_service import FSRSService
from app.schemas import ReviewRequest

router = APIRouter(prefix="/api/study", tags=["Study"])
fsrs_service = FSRSService()


@router.get("/queue")
def get_study_queue(
    new_limit: int = 10,
    review_limit: int = 50,
    category_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get today's study queue, with optional category/tag/search filters"""
    questions = fsrs_service.get_learning_queue(
        db, new_limit, review_limit,
        category_id=category_id, tag_id=tag_id, search=search
    )

    return [
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
            "pdf_id": q.pdf_id,
            "is_new": not hasattr(q, 'progress') or q.progress is None or q.progress.state == 0
        }
        for q in questions
    ]


@router.get("/due-count")
def get_due_count(db: Session = Depends(get_db)):
    """Get today's due question count"""
    from datetime import datetime
    due = db.query(UserProgress).filter(
        UserProgress.due_date <= datetime.utcnow()
    ).count()

    new_count = db.query(Question).outerjoin(
        UserProgress, Question.id == UserProgress.question_id
    ).filter(UserProgress.id == None).count()

    return {
        "due_today": due,
        "new_questions": new_count,
        "total": due + new_count
    }


@router.post("/review")
def review_question(
    request: ReviewRequest,
    db: Session = Depends(get_db)
):
    """Submit answer, system auto-rates and runs FSRS scheduling.
    
    Request body:
      - question_id: int
      - selected_answer: str (e.g. "A", "AB", "True", or text)
      - used_time_sec: int
      - is_practice: bool (if True, only log + tag, skip FSRS scheduling)
    
    The system compares selected_answer with the correct answer,
    auto-rates (Again/Hard/Good/Easy) based on correctness + speed,
    then runs FSRS scheduling and auto-tags the question.
    
    In practice mode (is_practice=True), FSRS scheduling is skipped to
    avoid polluting the spaced repetition data. Only ReviewLog and tags
    are updated.
    """
    q = db.query(Question).filter(Question.id == request.question_id).first()
    if not q:
        raise HTTPException(404, "Question not found")

    # Auto-rate: system judges correctness + speed -> FSRS rating 1-4
    rating = fsrs_service.auto_rate(
        correct_answer=q.answer,
        selected_answer=request.selected_answer,
        used_time_sec=request.used_time_sec or 0
    )

    # Log review record (always, for both practice and study modes)
    fsrs_service.log_review(db, request.question_id, rating, request.used_time_sec or 0)

    if request.is_practice:
        # Practice mode: only log + tag, skip FSRS scheduling
        # Still tag Wrong questions so they appear in error notebook
        if rating == 1:
            # Need a progress object for auto_tag, create if not exists but don't run FSRS
            progress = db.query(UserProgress).filter(
                UserProgress.question_id == request.question_id
            ).first()
            if progress:
                fsrs_service.auto_tag(db, request.question_id, rating, progress)
        db.commit()

        is_correct = rating > 1
        rating_labels = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
        return {
            "message": "Practice review logged (FSRS skipped)",
            "is_correct": is_correct,
            "correct_answer": q.answer,
            "auto_rating": rating,
            "auto_rating_label": rating_labels.get(rating, "Unknown"),
            "next_due": None,
            "next_interval_days": 0,
            "state": 0,
            "reps": 0,
            "lapses": 0
        }

    # Study mode: full FSRS scheduling
    # Get or create progress record
    progress = db.query(UserProgress).filter(
        UserProgress.question_id == request.question_id
    ).first()

    if not progress:
        progress = fsrs_service.create_progress(db, request.question_id)

    # FSRS review calculation
    progress = fsrs_service.review(progress, rating)

    # Auto-tag based on result
    fsrs_service.auto_tag(db, request.question_id, rating, progress)

    db.commit()

    # Determine if the answer was correct for frontend feedback
    is_correct = rating > 1  # Again = wrong, Hard/Good/Easy = correct

    rating_labels = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}

    return {
        "message": "Review record updated",
        "is_correct": is_correct,
        "correct_answer": q.answer,
        "auto_rating": rating,
        "auto_rating_label": rating_labels.get(rating, "Unknown"),
        "next_due": progress.due_date.isoformat() if progress.due_date else None,
        "next_interval_days": progress.next_interval,
        "state": progress.state,
        "reps": progress.reps,
        "lapses": progress.lapses
    }


@router.get("/stats")
def get_study_stats(db: Session = Depends(get_db)):
    """Get study statistics"""
    return fsrs_service.get_stats(db)


@router.get("/stats/by-category")
def get_stats_by_category(db: Session = Depends(get_db)):
    """Get study progress stats by category"""
    from sqlalchemy import func
    from app.models import Category

    from sqlalchemy import case as sql_case
    results = db.query(
        Category.id,
        Category.name,
        func.count(Question.id).label("total"),
        func.count(UserProgress.id).label("learned"),
        func.sum(sql_case((UserProgress.stability > 100, 1), else_=0)).label("mastered")
    ).outerjoin(Question, Category.id == Question.category_id
    ).outerjoin(UserProgress, Question.id == UserProgress.question_id
    ).group_by(Category.id).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "total": r.total or 0,
            "learned": r.learned or 0,
            "mastered": r.mastered or 0,
            "progress_rate": round((r.learned or 0) / r.total * 100, 1) if r.total else 0
        }
        for r in results
    ]


@router.get("/review-history")
def get_review_history(
    question_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get review history"""
    query = db.query(ReviewLog).order_by(ReviewLog.review_time.desc())

    if question_id:
        query = query.filter(ReviewLog.question_id == question_id)

    logs = query.limit(limit).all()

    return [
        {
            "id": l.id,
            "question_id": l.question_id,
            "question_text": l.question.question_text if l.question else None,
            "rating": l.rating,
            "review_time": l.review_time.isoformat() if l.review_time else None,
            "used_time_sec": l.used_time_sec
        }
        for l in logs
    ]


@router.get("/wrong-questions")
def get_wrong_questions(
    limit: int = 50,
    category_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get wrong/confusing questions for error-prone practice mode.
    
    Returns questions tagged 'Wrong' or 'Confusing', ordered by most recent review.
    Supports optional category/tag/search filters.
    """
    from app.models import Tag
    wrong_tag = db.query(Tag).filter(Tag.name == "Wrong").first()
    confusing_tag = db.query(Tag).filter(Tag.name == "Confusing").first()

    tag_ids = []
    if wrong_tag:
        tag_ids.append(wrong_tag.id)
    if confusing_tag:
        tag_ids.append(confusing_tag.id)

    if not tag_ids:
        return []

    query = db.query(Question).join(
        question_tags, Question.id == question_tags.c.question_id
    ).filter(
        question_tags.c.tag_id.in_(tag_ids)
    ).distinct()

    if category_id:
        query = query.filter(Question.category_id == category_id)

    if search:
        query = query.filter(Question.question_text.contains(search))

    # If user wants to further filter by a specific tag (not Wrong/Confusing)
    if tag_id and tag_id not in tag_ids:
        query = query.join(question_tags, Question.id == question_tags.c.question_id, isouter=False).filter(
            question_tags.c.tag_id == tag_id
        )

    questions = query.limit(limit).all()

    return [
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
            "pdf_id": q.pdf_id,
            "is_new": False,
            "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in q.tags]
        }
        for q in questions
    ]


@router.get("/session-summary")
def get_session_summary(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get study session summary for the last N hours.
    
    Returns: total reviewed, correct count, wrong count, avg time, by-category breakdown.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func, case as sql_case

    since = datetime.utcnow() - timedelta(hours=hours)

    logs = db.query(ReviewLog).filter(ReviewLog.review_time >= since).all()

    total = len(logs)
    if total == 0:
        return {
            "total": 0,
            "correct": 0,
            "wrong": 0,
            "accuracy": 0,
            "avg_time_sec": 0,
            "by_category": [],
            "rating_distribution": {}
        }

    correct = sum(1 for l in logs if l.rating > 1)
    wrong = total - correct
    avg_time = sum(l.used_time_sec or 0 for l in logs) / total
    accuracy = round(correct / total * 100, 1)

    # Rating distribution
    rating_dist = {}
    for l in logs:
        label = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}.get(l.rating, "Unknown")
        rating_dist[label] = rating_dist.get(label, 0) + 1

    # By category breakdown
    cat_stats = db.query(
        Category.name,
        func.count(ReviewLog.id).label("count"),
        func.sum(sql_case((ReviewLog.rating > 1, 1), else_=0)).label("correct")
    ).join(Question, ReviewLog.question_id == Question.id
    ).join(Category, Question.category_id == Category.id
    ).filter(ReviewLog.review_time >= since
    ).group_by(Category.id).all()

    by_category = [
        {
            "name": r.name,
            "total": r.count,
            "correct": r.correct or 0,
            "accuracy": round((r.correct or 0) / r.count * 100, 1) if r.count else 0
        }
        for r in cat_stats
    ]

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy,
        "avg_time_sec": round(avg_time, 1),
        "rating_distribution": rating_dist,
        "by_category": by_category
    }
