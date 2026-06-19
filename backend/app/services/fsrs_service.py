# -*- coding: utf-8 -*-
"""FSRS spaced repetition algorithm service - adapted for fsrs v4+"""
from datetime import datetime, timedelta
from typing import Optional, List
from fsrs import Scheduler, Card, Rating, State
from sqlalchemy.orm import Session
from app.models import UserProgress, Question, ReviewLog, Tag, question_tags
from app.config import get_settings

settings = get_settings()

# FSRS rating mapping (1-4)
RATING_MAP = {
    1: Rating.Again,   # Forgot - completely don't know
    2: Rating.Hard,    # Hard - barely recalled
    3: Rating.Good,    # Good - normal recall
    4: Rating.Easy,    # Easy - instant recall
}

# State enum mapping (v4+ State has no New)
INT_STATE_MAP = {
    State.Learning: 1,
    State.Review: 2,
    State.Relearning: 3,
}

# Time thresholds (seconds) for auto-rating correct answers
EASY_THRESHOLD = 10   # < 10s -> Easy
GOOD_THRESHOLD = 30   # < 30s -> Good, else Hard


class FSRSService:
    """FSRS scheduling service"""

    def __init__(self):
        self.scheduler = Scheduler()

    def _build_card(self, progress: UserProgress) -> Card:
        """Build FSRS Card from database progress"""
        from datetime import timezone as _tz

        card = Card()

        if progress.due_date:
            # FSRS expects timezone-aware UTC datetimes
            due = progress.due_date
            if due.tzinfo is None:
                due = due.replace(tzinfo=_tz.utc)
            card.due = due
        if progress.stability and progress.stability > 0:
            card.stability = progress.stability
        if progress.difficulty_fsrs and progress.difficulty_fsrs > 0:
            card.difficulty = progress.difficulty_fsrs
        if progress.last_review:
            # FSRS expects timezone-aware UTC datetimes
            last = progress.last_review
            if last.tzinfo is None:
                last = last.replace(tzinfo=_tz.utc)
            card.last_review = last

        return card

    def review(self, progress: UserProgress, rating_value: int) -> UserProgress:
        """Process review, update FSRS state"""

        # Build FSRS Card
        card = self._build_card(progress)

        # Get Rating
        rating = RATING_MAP.get(rating_value, Rating.Good)

        # FSRS calculation
        now = datetime.utcnow()
        new_card, review_log = self.scheduler.review_card(card, rating)

        # new_card.due may be offset-aware (from FSRS library), normalize to naive
        due = new_card.due
        if due.tzinfo is not None:
            due = due.replace(tzinfo=None)

        # Update progress
        progress.due_date = due
        progress.stability = new_card.stability or 0.0
        progress.difficulty_fsrs = new_card.difficulty or 0.0
        progress.state = INT_STATE_MAP.get(new_card.state, 1)
        progress.last_review = now
        progress.next_interval = max(0, (due - now).days)

        # Increment reps and lapses
        progress.reps = (progress.reps or 0) + 1

        # If rating is Again, increment lapse count
        if rating == Rating.Again:
            progress.lapses = (progress.lapses or 0) + 1

        return progress

    def get_due_questions(self, db: Session, limit: int = 50,
                          category_id: Optional[int] = None,
                          tag_id: Optional[int] = None,
                          search: Optional[str] = None) -> List[Question]:
        """Get questions due for review today, with optional filters.
        
        Sorting: Review-stage (state==2) by stability asc (least stable first),
        Learning-stage (state!=2) by due_date asc.
        """
        from sqlalchemy import case as sql_case
        now = datetime.utcnow()

        query = db.query(UserProgress).filter(
            UserProgress.due_date <= now
        ).order_by(
            sql_case((UserProgress.state == 2, 0), else_=1),  # Review stage first
            sql_case((UserProgress.state == 2, UserProgress.stability), else_=0).asc(),  # stability for Review
            UserProgress.due_date.asc()  # due_date for Learning / tiebreaker
        )

        progress_list = query.limit(limit * 3).all()  # over-fetch to allow filtering

        questions = []
        for p in progress_list:
            if not p.question:
                continue
            q = p.question
            if category_id and q.category_id != category_id:
                continue
            if search and search not in (q.question_text or ''):
                continue
            if tag_id:
                tag_ids = {t.id for t in q.tags}
                if tag_id not in tag_ids:
                    continue
            questions.append(q)
            if len(questions) >= limit:
                break

        return questions

    def get_new_questions(self, db: Session, limit: int = 20,
                          category_id: Optional[int] = None,
                          tag_id: Optional[int] = None,
                          search: Optional[str] = None) -> List[Question]:
        """Get unlearned new questions, continuing from last learned position.
        
        Finds the max question_id already in UserProgress, then fetches
        new questions with id > that position, preserving chapter order.
        """
        from sqlalchemy import select, func

        # Find the last learned question position
        max_learned_id = db.query(func.max(UserProgress.question_id)).scalar() or 0

        subquery = select(UserProgress.question_id)

        query = db.query(Question).filter(
            ~Question.id.in_(subquery)
        )

        if category_id:
            query = query.filter(Question.category_id == category_id)

        if search:
            query = query.filter(Question.question_text.contains(search))

        if tag_id:
            query = query.join(question_tags).filter(question_tags.c.tag_id == tag_id)

        # Prioritize questions after the last learned position (continue where left off)
        # If not enough, wrap around to the beginning
        from sqlalchemy import case as sql_case
        query = query.order_by(
            sql_case((Question.id > max_learned_id, 0), else_=1),
            Question.id.asc()
        )

        new_questions = query.limit(limit).all()

        return new_questions

    def get_learning_queue(self, db: Session, new_limit: int = 10, review_limit: int = 50,
                           category_id: Optional[int] = None,
                           tag_id: Optional[int] = None,
                           search: Optional[str] = None) -> List[Question]:
        """Get learning queue: new questions + due review questions, with optional filters"""
        # Get due review questions first
        due = self.get_due_questions(db, review_limit, category_id, tag_id, search)

        # Then supplement with new questions
        remaining = new_limit + review_limit - len(due)
        if remaining > 0:
            new_qs = self.get_new_questions(db, remaining, category_id, tag_id, search)
            # Merge and deduplicate
            seen = {q.id for q in due}
            for q in new_qs:
                if q.id not in seen:
                    due.append(q)

        return due[:new_limit + review_limit]

    def get_stats(self, db: Session) -> dict:
        """Get study statistics"""
        total = db.query(Question).count()
        progress_count = db.query(UserProgress).count()
        learned = db.query(UserProgress).filter(UserProgress.last_review != None).count()
        due_today = db.query(UserProgress).filter(
            UserProgress.due_date <= datetime.utcnow()
        ).count()
        new_count = total - progress_count

        # Calculate mastery rate (stability > 100 days considered mastered)
        mastered = db.query(UserProgress).filter(
            UserProgress.stability > 100
        ).count()

        return {
            "total_questions": total,
            "learned": learned,
            "due_today": due_today,
            "new_questions": max(0, new_count),
            "mastered": mastered,
            "master_rate": round(mastered / total * 100, 1) if total > 0 else 0
        }

    def create_progress(self, db: Session, question_id: int) -> UserProgress:
        """Create learning progress record for new question.
        Uses flush() instead of commit() so caller can manage the transaction.
        """
        progress = UserProgress(
            question_id=question_id,
            due_date=datetime.utcnow(),
            state=0,
            stability=0.0,
            difficulty_fsrs=0.0,
            reps=0,
            lapses=0,
            next_interval=0
        )
        db.add(progress)
        db.flush()
        return progress

    def log_review(self, db: Session, question_id: int, rating: int, used_time: int = 0) -> ReviewLog:
        """Log review record (no commit - caller manages transaction)"""
        log = ReviewLog(
            question_id=question_id,
            rating=rating,
            used_time_sec=used_time
        )
        db.add(log)
        db.flush()
        return log

    def auto_rate(self, correct_answer: str, selected_answer: str, used_time_sec: int) -> int:
        """Auto-rate based on correctness and response time.
        
        Returns FSRS rating 1-4:
          1 = Again (wrong)
          2 = Hard (correct but slow > 30s)
          3 = Good (correct, 10-30s)
          4 = Easy (correct, < 10s)
        """
        correct = correct_answer.strip().upper()
        selected = selected_answer.strip().upper()

        # Normalize: extract just the letter(s) from selected answer
        # e.g. "A. Some text" -> "A", "AB" -> "AB"
        if not selected:
            return 1  # No answer = wrong

        # Extract only uppercase letters (A-E) from both, ignore punctuation/text
        import re as _re
        correct_letters = "".join(sorted(_re.findall(r"[A-E]", correct)))
        selected_letters = "".join(sorted(_re.findall(r"[A-E]", selected)))

        # Exact match after sorting (so "BA" == "AB" for multiple choice)
        is_correct = (correct_letters != "" and correct_letters == selected_letters)

        if not is_correct:
            return 1  # Again - wrong answer

        # Correct answer - rate by speed
        if used_time_sec < EASY_THRESHOLD:
            return 4  # Easy - fast correct
        elif used_time_sec < GOOD_THRESHOLD:
            return 3  # Good - normal speed
        else:
            return 2  # Hard - slow but correct

    def auto_tag(self, db: Session, question_id: int, rating: int, progress: UserProgress):
        """Auto-assign tags based on review result.
        
        - rating == 1 (Again): tag "Wrong" if not already tagged
        - reps >= 3 and lapses == 0: tag "Mastered"
        - lapses >= 2: tag "Confusing" (repeatedly wrong)
        """
        tag_rules = [
            ("Wrong", rating == 1),
            ("Confusing", (progress.lapses or 0) >= 2),
            ("Mastered", (progress.reps or 0) >= 3 and (progress.lapses or 0) == 0),
        ]

        for tag_name, should_tag in tag_rules:
            if not should_tag:
                continue
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, color={
                    "Wrong": "#EF4444",
                    "Confusing": "#8B5CF6",
                    "Mastered": "#10B981",
                }.get(tag_name, "#3B82F6"))
                db.add(tag)
                db.flush()

            # Check if question already has this tag
            question = db.query(Question).filter(Question.id == question_id).first()
            if question and tag not in question.tags:
                question.tags.append(tag)

        # No commit - caller manages transaction
