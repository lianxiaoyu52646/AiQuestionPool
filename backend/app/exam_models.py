# -*- coding: utf-8 -*-
"""Database models for exam simulation (真题模考)"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ExamPaper(Base):
    """真题试卷表"""
    __tablename__ = "exam_papers"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(100), nullable=False)  # 科目: 中药学专业知识一/二/综合
    year = Column(Integer, nullable=False)  # 年份: 2020-2024
    title = Column(String(200), nullable=False)  # 试卷标题
    description = Column(Text, default="")
    total_questions = Column(Integer, default=120)
    time_limit_minutes = Column(Integer, default=120)  # 考试时长(分钟)
    pass_score = Column(Integer, default=72)  # 合格分数线
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship("ExamQuestion", back_populates="paper", cascade="all, delete-orphan")
    attempts = relationship("ExamAttempt", back_populates="paper", cascade="all, delete-orphan")


class ExamQuestion(Base):
    """真题题目表"""
    __tablename__ = "exam_questions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False)
    question_number = Column(Integer, nullable=False)  # 题号 1-120
    question_type = Column(String(10), nullable=False)  # A/B/C/X 型题
    stem = Column(Text, nullable=False)  # 题干
    options = Column(JSON, default=dict)  # {"A": "...", "B": "...", ...}
    answer = Column(String(20), nullable=False)  # 正确答案: "A" or "ABCD"
    explanation = Column(Text, default="")  # 解析

    # B型题(配伍选择题)和C型题(综合分析选择题)的分组信息
    group_id = Column(String(50), nullable=True)  # 同一共享题干的题目分组ID
    shared_stem = Column(Text, nullable=True)  # 共享题干(B/C型题)

    paper = relationship("ExamPaper", back_populates="questions")


class ExamAttempt(Base):
    """考试记录表"""
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    time_used_seconds = Column(Integer, default=0)  # 实际用时(秒)
    status = Column(String(20), default="in_progress")  # in_progress / finished / abandoned

    total_answered = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    unanswered = Column(Integer, default=0)
    score = Column(Integer, default=0)  # 得分

    answers = relationship("ExamAnswer", back_populates="attempt", cascade="all, delete-orphan")
    paper = relationship("ExamPaper", back_populates="attempts")


class ExamAnswer(Base):
    """答题记录表"""
    __tablename__ = "exam_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("exam_questions.id"), nullable=False)
    user_answer = Column(String(20), default="")  # 用户选择的答案
    is_correct = Column(Boolean, default=None)  # 是否正确(None=未作答)
    answered_at = Column(DateTime, default=datetime.utcnow)

    attempt = relationship("ExamAttempt", back_populates="answers")
