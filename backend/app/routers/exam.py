# -*- coding: utf-8 -*-
"""Exam simulation routes (真题模考)"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from app.database import get_db
from app.exam_models import ExamPaper, ExamQuestion, ExamAttempt, ExamAnswer

router = APIRouter(prefix="/api/exam", tags=["Exam"])


def ensure_options_dict(opts):
    """确保options字段为dict类型（处理可能的双重JSON编码）"""
    if opts is None:
        return {}
    if isinstance(opts, dict):
        return opts
    if isinstance(opts, str):
        try:
            parsed = json.loads(opts)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


# ========== Schemas ==========

class PaperListItem(BaseModel):
    id: int
    subject: str
    year: int
    title: str
    total_questions: int
    time_limit_minutes: int
    pass_score: int
    question_count: int = 0
    attempt_count: int = 0

    class Config:
        from_attributes = True


class QuestionItem(BaseModel):
    id: int
    question_number: int
    question_type: str
    stem: str
    options: dict
    answer: str = ""
    explanation: str = ""
    group_id: Optional[str] = None
    shared_stem: Optional[str] = None

    class Config:
        from_attributes = True


class PaperDetail(BaseModel):
    id: int
    subject: str
    year: int
    title: str
    description: str
    total_questions: int
    time_limit_minutes: int
    pass_score: int
    questions: List[QuestionItem]

    class Config:
        from_attributes = True


class StartAttemptRequest(BaseModel):
    paper_id: int


class SubmitAnswerRequest(BaseModel):
    question_id: int
    user_answer: str


class SubmitAttemptRequest(BaseModel):
    paper_id: int
    answers: List[SubmitAnswerRequest]
    time_used_seconds: int = 0


class AnswerResult(BaseModel):
    question_id: int
    question_number: int
    question_type: str
    user_answer: str
    correct_answer: str
    is_correct: Optional[bool] = None  # None=未作答, True=正确, False=错误
    stem: str
    options: dict
    explanation: str
    shared_stem: Optional[str] = None


class AttemptResult(BaseModel):
    attempt_id: int
    paper_id: int
    paper_title: str
    total_questions: int
    total_answered: int
    correct_count: int
    wrong_count: int
    unanswered: int
    score: int
    pass_score: int
    passed: bool
    time_used_seconds: int
    started_at: datetime
    finished_at: Optional[datetime]
    answers: List[AnswerResult]


class AttemptListItem(BaseModel):
    id: int
    paper_id: int
    paper_title: str
    status: str
    score: int
    pass_score: int = 0
    correct_count: int
    wrong_count: int
    unanswered: int
    total_answered: int
    time_used_seconds: int
    started_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class SaveDraftRequest(BaseModel):
    paper_id: int
    answers: List[SubmitAnswerRequest]
    time_used_seconds: int = 0
    current_index: int = 0


class DraftResponse(BaseModel):
    attempt_id: int
    paper_id: int
    paper_title: str
    time_used_seconds: int
    current_index: int
    answers: List[SubmitAnswerRequest]
    started_at: datetime


# ========== Routes ==========

@router.get("/papers", response_model=List[PaperListItem])
def list_papers(db: Session = Depends(get_db)):
    """获取所有试卷列表"""
    papers = db.query(ExamPaper).order_by(ExamPaper.year.desc(), ExamPaper.subject).all()
    result = []
    for p in papers:
        q_count = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).count()
        a_count = db.query(ExamAttempt).filter(ExamAttempt.paper_id == p.id).count()
        result.append(PaperListItem(
            id=p.id,
            subject=p.subject,
            year=p.year,
            title=p.title,
            total_questions=p.total_questions,
            time_limit_minutes=p.time_limit_minutes,
            pass_score=p.pass_score,
            question_count=q_count,
            attempt_count=a_count,
        ))
    return result


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    """获取试卷详情（含所有题目，不含答案）"""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    questions = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper_id
    ).order_by(ExamQuestion.question_number).all()

    # 返回题目时不包含答案和解析（考试模式下）
    q_list = []
    for q in questions:
        q_list.append(QuestionItem(
            id=q.id,
            question_number=q.question_number,
            question_type=q.question_type,
            stem=q.stem,
            options=ensure_options_dict(q.options),
            answer="",  # 考试中不返回答案
            explanation="",  # 考试中不返回解析
            group_id=q.group_id,
            shared_stem=q.shared_stem,
        ))

    return PaperDetail(
        id=paper.id,
        subject=paper.subject,
        year=paper.year,
        title=paper.title,
        description=paper.description or "",
        total_questions=paper.total_questions,
        time_limit_minutes=paper.time_limit_minutes,
        pass_score=paper.pass_score,
        questions=q_list,
    )


@router.get("/papers/{paper_id}/review", response_model=PaperDetail)
def get_paper_review(paper_id: int, db: Session = Depends(get_db)):
    """获取试卷详情（含答案和解析，用于查看/复习模式）"""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    questions = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper_id
    ).order_by(ExamQuestion.question_number).all()

    q_list = []
    for q in questions:
        q_list.append(QuestionItem(
            id=q.id,
            question_number=q.question_number,
            question_type=q.question_type,
            stem=q.stem,
            options=ensure_options_dict(q.options),
            answer=q.answer,
            explanation=q.explanation or "",
            group_id=q.group_id,
            shared_stem=q.shared_stem,
        ))

    return PaperDetail(
        id=paper.id,
        subject=paper.subject,
        year=paper.year,
        title=paper.title,
        description=paper.description or "",
        total_questions=paper.total_questions,
        time_limit_minutes=paper.time_limit_minutes,
        pass_score=paper.pass_score,
        questions=q_list,
    )


@router.post("/drafts", response_model=DraftResponse)
def save_draft(req: SaveDraftRequest, db: Session = Depends(get_db)):
    """保存考试草稿（退出时保存进度）"""
    paper = db.query(ExamPaper).filter(ExamPaper.id == req.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 查找该试卷是否有未完成的草稿
    draft = db.query(ExamAttempt).filter(
        ExamAttempt.paper_id == req.paper_id,
        ExamAttempt.status == "in_progress"
    ).first()

    now = datetime.utcnow()
    from datetime import timedelta
    started_at = now - timedelta(seconds=req.time_used_seconds) if req.time_used_seconds > 0 else now

    if draft:
        # 更新已有草稿
        draft.time_used_seconds = req.time_used_seconds
        draft.started_at = started_at
        # 清除旧答案
        db.query(ExamAnswer).filter(ExamAnswer.attempt_id == draft.id).delete()
        db.flush()
    else:
        # 创建新草稿
        draft = ExamAttempt(
            paper_id=req.paper_id,
            started_at=started_at,
            finished_at=None,
            time_used_seconds=req.time_used_seconds,
            status="in_progress",
        )
        db.add(draft)
        db.flush()

    # 保存答案
    for a in req.answers:
        if a.user_answer:
            exam_answer = ExamAnswer(
                attempt_id=draft.id,
                question_id=a.question_id,
                user_answer=a.user_answer,
                is_correct=None,
            )
            db.add(exam_answer)

    db.commit()
    db.refresh(draft)

    # 返回草稿数据
    saved_answers = db.query(ExamAnswer).filter(ExamAnswer.attempt_id == draft.id).all()
    return DraftResponse(
        attempt_id=draft.id,
        paper_id=paper.id,
        paper_title=paper.title,
        time_used_seconds=draft.time_used_seconds,
        current_index=req.current_index,
        answers=[SubmitAnswerRequest(question_id=a.question_id, user_answer=a.user_answer) for a in saved_answers],
        started_at=draft.started_at,
    )


@router.get("/drafts/{paper_id}", response_model=Optional[DraftResponse])
def get_draft(paper_id: int, db: Session = Depends(get_db)):
    """获取试卷的未完成草稿"""
    draft = db.query(ExamAttempt).filter(
        ExamAttempt.paper_id == paper_id,
        ExamAttempt.status == "in_progress"
    ).first()

    if not draft:
        return None

    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    saved_answers = db.query(ExamAnswer).filter(ExamAnswer.attempt_id == draft.id).all()

    return DraftResponse(
        attempt_id=draft.id,
        paper_id=paper_id,
        paper_title=paper.title if paper else "",
        time_used_seconds=draft.time_used_seconds,
        current_index=0,
        answers=[SubmitAnswerRequest(question_id=a.question_id, user_answer=a.user_answer) for a in saved_answers],
        started_at=draft.started_at,
    )


@router.delete("/drafts/{paper_id}")
def delete_draft(paper_id: int, db: Session = Depends(get_db)):
    """删除试卷的未完成草稿"""
    draft = db.query(ExamAttempt).filter(
        ExamAttempt.paper_id == paper_id,
        ExamAttempt.status == "in_progress"
    ).first()

    if not draft:
        return {"detail": "无草稿"}

    db.query(ExamAnswer).filter(ExamAnswer.attempt_id == draft.id).delete()
    db.delete(draft)
    db.commit()
    return {"detail": "草稿已删除"}


@router.post("/attempts", response_model=AttemptResult)
def submit_attempt(req: SubmitAttemptRequest, db: Session = Depends(get_db)):
    """提交答卷，自动判分"""
    paper = db.query(ExamPaper).filter(ExamPaper.id == req.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    questions = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == req.paper_id
    ).order_by(ExamQuestion.question_number).all()

    if not questions:
        raise HTTPException(status_code=400, detail="试卷没有题目")

    # 检查是否有已有草稿，如果有则复用
    existing_draft = db.query(ExamAttempt).filter(
        ExamAttempt.paper_id == req.paper_id,
        ExamAttempt.status == "in_progress"
    ).first()

    now = datetime.utcnow()
    from datetime import timedelta
    # 根据前端传来的用时反推开始时间（直接计算，不截断）
    started_at = now - timedelta(seconds=req.time_used_seconds) if req.time_used_seconds > 0 else now

    if existing_draft:
        # 复用草稿记录，清除旧答案
        attempt = existing_draft
        attempt.started_at = started_at
        attempt.finished_at = now
        attempt.time_used_seconds = req.time_used_seconds
        attempt.status = "finished"
        db.query(ExamAnswer).filter(ExamAnswer.attempt_id == attempt.id).delete()
        db.flush()
    else:
        attempt = ExamAttempt(
            paper_id=req.paper_id,
            started_at=started_at,
            finished_at=now,
            time_used_seconds=req.time_used_seconds,
            status="finished",
        )
        db.add(attempt)
        db.flush()

    # 构建答案映射
    answer_map = {a.question_id: a.user_answer.strip().upper() for a in req.answers}

    correct_count = 0
    wrong_count = 0
    unanswered = 0
    answer_results = []

    for q in questions:
        user_ans = answer_map.get(q.id, "")

        if not user_ans:
            unanswered += 1
            is_correct = False
        else:
            # 比较答案（X型题需要排序比较）
            correct_answer = q.answer.strip().upper()
            # 将用户答案和正确答案都排序后比较
            user_sorted = "".join(sorted(user_ans))
            correct_sorted = "".join(sorted(correct_answer))
            is_correct = (user_sorted == correct_sorted)

            if is_correct:
                correct_count += 1
            else:
                wrong_count += 1

        exam_answer = ExamAnswer(
            attempt_id=attempt.id,
            question_id=q.id,
            user_answer=user_ans,
            is_correct=is_correct if user_ans else None,
        )
        db.add(exam_answer)

        answer_results.append(AnswerResult(
            question_id=q.id,
            question_number=q.question_number,
            question_type=q.question_type,
            user_answer=user_ans,
            correct_answer=q.answer,
            is_correct=is_correct if user_ans else None,  # 未作答返回 None
            stem=q.stem,
            options=ensure_options_dict(q.options),
            explanation=q.explanation or "",
            shared_stem=q.shared_stem,
        ))

    total_answered = correct_count + wrong_count
    # 每题1分
    score = correct_count

    attempt.total_answered = total_answered
    attempt.correct_count = correct_count
    attempt.wrong_count = wrong_count
    attempt.unanswered = unanswered
    attempt.score = score
    attempt.time_used_seconds = req.time_used_seconds

    db.commit()
    db.refresh(attempt)

    return AttemptResult(
        attempt_id=attempt.id,
        paper_id=paper.id,
        paper_title=paper.title,
        total_questions=len(questions),
        total_answered=total_answered,
        correct_count=correct_count,
        wrong_count=wrong_count,
        unanswered=unanswered,
        score=score,
        pass_score=paper.pass_score,
        passed=score >= paper.pass_score,
        time_used_seconds=attempt.time_used_seconds,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        answers=answer_results,
    )


@router.get("/attempts", response_model=List[AttemptListItem])
def list_attempts(
    paper_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """获取考试记录列表"""
    query = db.query(ExamAttempt)
    if paper_id:
        query = query.filter(ExamAttempt.paper_id == paper_id)
    attempts = query.order_by(ExamAttempt.finished_at.desc()).limit(limit).all()

    result = []
    for a in attempts:
        paper = db.query(ExamPaper).filter(ExamPaper.id == a.paper_id).first()
        result.append(AttemptListItem(
            id=a.id,
            paper_id=a.paper_id,
            paper_title=paper.title if paper else "",
            status=a.status,
            score=a.score,
            pass_score=paper.pass_score if paper else 0,
            correct_count=a.correct_count,
            wrong_count=a.wrong_count,
            unanswered=a.unanswered,
            total_answered=a.total_answered,
            time_used_seconds=a.time_used_seconds,
            started_at=a.started_at,
            finished_at=a.finished_at,
        ))
    return result


@router.get("/attempts/{attempt_id}", response_model=AttemptResult)
def get_attempt_detail(attempt_id: int, db: Session = Depends(get_db)):
    """获取考试记录详情（含每题答题情况）"""
    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    paper = db.query(ExamPaper).filter(ExamPaper.id == attempt.paper_id).first()
    questions = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == attempt.paper_id
    ).order_by(ExamQuestion.question_number).all()

    # 构建答题映射
    answer_records = db.query(ExamAnswer).filter(
        ExamAnswer.attempt_id == attempt_id
    ).all()
    answer_map = {a.question_id: a for a in answer_records}

    answer_results = []
    for q in questions:
        record = answer_map.get(q.id)
        user_ans = record.user_answer if record else ""
        is_correct = record.is_correct if record else None

        answer_results.append(AnswerResult(
            question_id=q.id,
            question_number=q.question_number,
            question_type=q.question_type,
            user_answer=user_ans,
            correct_answer=q.answer,
            is_correct=is_correct,  # None=未作答, True/False=已作答
            stem=q.stem,
            options=ensure_options_dict(q.options),
            explanation=q.explanation or "",
            shared_stem=q.shared_stem,
        ))

    return AttemptResult(
        attempt_id=attempt.id,
        paper_id=paper.id,
        paper_title=paper.title,
        total_questions=len(questions),
        total_answered=attempt.total_answered,
        correct_count=attempt.correct_count,
        wrong_count=attempt.wrong_count,
        unanswered=attempt.unanswered,
        score=attempt.score,
        pass_score=paper.pass_score,
        passed=attempt.score >= paper.pass_score,
        time_used_seconds=attempt.time_used_seconds,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        answers=answer_results,
    )
