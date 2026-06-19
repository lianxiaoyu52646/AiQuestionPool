# -*- coding: utf-8 -*-
"""Database models"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Table, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

# Question-Tag association table
question_tags = Table(
    "question_tags",
    Base.metadata,
    Column("question_id", Integer, ForeignKey("questions.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)


class PDFFile(Base):
    """PDF files table"""
    __tablename__ = "pdf_files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    total_pages = Column(Integer, default=0)
    upload_time = Column(DateTime, default=datetime.utcnow)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    # PDF type: 'question' (题目PDF), 'answer' (答案PDF), 'combined' (题答合一)
    pdf_type = Column(String(20), default="combined")
    # Linked PDF ID: if this is an answer PDF, which question PDF does it belong to?
    linked_pdf_id = Column(Integer, ForeignKey("pdf_files.id"), nullable=True)
    
    # Async parsing status: pending / parsing / completed / failed
    parse_status = Column(String(20), default="pending")
    parse_progress = Column(Integer, default=0)  # 0-100
    parsed_questions = Column(Integer, default=0)
    parse_error = Column(Text, default="")
    
    categories = relationship("Category", back_populates="pdf", foreign_keys="Category.pdf_id")
    questions = relationship("Question", back_populates="pdf")


class Category(Base):
    """Category/Chapters table"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    pdf_id = Column(Integer, ForeignKey("pdf_files.id"), nullable=False)
    order_index = Column(Integer, default=0)
    
    pdf = relationship("PDFFile", back_populates="categories", foreign_keys=[pdf_id])
    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent")
    questions = relationship("Question", back_populates="category")


class Question(Base):
    """Questions table"""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdf_files.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, default=list)
    answer = Column(String(50), nullable=True)  # nullable: question PDF may not have answers yet
    explanation = Column(Text, default="")
    question_type = Column(String(20), default="single")
    page_number = Column(Integer, default=0)
    difficulty = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Matching key for cross-PDF answer matching
    question_number = Column(String(50), default="")  # e.g. "1", "2", "101"
    chapter = Column(String(200), default="")  # e.g. "第一章执业药师与中药药学服务"
    section = Column(String(200), default="")  # e.g. "第一节 中药药学服务及其模式"
    
    pdf = relationship("PDFFile", back_populates="questions")
    category = relationship("Category", back_populates="questions")
    progress = relationship("UserProgress", back_populates="question", uselist=False)
    tags = relationship("Tag", secondary=question_tags, back_populates="questions")
    review_logs = relationship("ReviewLog", back_populates="question")


class UserProgress(Base):
    """User progress table (FSRS core)"""
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), unique=True, nullable=False)
    due_date = Column(DateTime, default=datetime.utcnow)
    stability = Column(Float, default=0.0)
    difficulty_fsrs = Column(Float, default=0.0)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    state = Column(Integer, default=0)
    last_review = Column(DateTime, nullable=True)
    next_interval = Column(Integer, default=0)
    
    question = relationship("Question", back_populates="progress")


class Tag(Base):
    """Tags table"""
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    color = Column(String(20), default="#3B82F6")
    
    questions = relationship("Question", secondary=question_tags, back_populates="tags")


class ReviewLog(Base):
    """Review logs table"""
    __tablename__ = "review_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    review_time = Column(DateTime, default=datetime.utcnow)
    used_time_sec = Column(Integer, default=0)
    
    question = relationship("Question", back_populates="review_logs")


# === Agent tables (multi-agent parallel parsing + memory compression) ===

class AgentSession(Base):
    """Agent session: one parsing task = one session.
    
    Supports breakpoint resume: if interrupted, can re-run and continue
    from where it left off using TaskState records.
    """
    __tablename__ = "agent_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdf_files.id"), nullable=False)
    task_type = Column(String(50), default="parse_questions")  # parse_questions / parse_answers / match_answers
    status = Column(String(20), default="pending")  # pending / running / paused / completed / failed
    total_chunks = Column(Integer, default=0)
    done_chunks = Column(Integer, default=0)
    failed_chunks = Column(Integer, default=0)
    
    # Memory management: track accumulated token usage
    total_tokens_used = Column(Integer, default=0)
    memory_compressed_count = Column(Integer, default=0)  # how many times memory was compressed
    
    # Summary after completion
    result_summary = Column(Text, default="")
    error_message = Column(Text, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    tasks = relationship("TaskState", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("AgentMessage", back_populates="session", cascade="all, delete-orphan")


class TaskState(Base):
    """Individual chunk/task state within a session.
    
    This is the core of breakpoint resume: each chunk is a row.
    When re-running, we skip 'done' chunks and retry 'failed' ones.
    """
    __tablename__ = "task_states"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # 0-based chunk index
    chunk_label = Column(String(100), default="")  # e.g. "chunk 1/20 (pages 1-5)"
    
    status = Column(String(20), default="pending")  # pending / running / done / failed
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Worker assignment (for parallel agents)
    worker_id = Column(String(50), nullable=True)  # which agent worker picked this up
    
    # Results
    questions_extracted = Column(Integer, default=0)
    result_summary = Column(Text, default="")  # brief summary of what happened
    error_message = Column(Text, default="")
    
    # ReAct trail: JSON array of {thought, action, observation}
    react_steps = Column(JSON, default=list)
    
    # Token usage for this chunk
    tokens_used = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    session = relationship("AgentSession", back_populates="tasks")


class AgentMessage(Base):
    """Agent message log: ReAct trail + memory management.
    
    When total tokens in a session exceed threshold, oldest 30% of messages
    are sent to GLM for compression into a summary.
    """
    __tablename__ = "agent_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=False)
    
    role = Column(String(20), nullable=False)  # thought / action / observation / system / summary
    content = Column(Text, nullable=False)
    
    # Token estimate for this message
    token_estimate = Column(Integer, default=0)
    
    # Whether this message has been compressed into a summary
    is_compressed = Column(Integer, default=0)  # 0=active, 1=compressed/archived
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("AgentSession", back_populates="messages")
