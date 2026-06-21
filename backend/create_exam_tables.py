# -*- coding: utf-8 -*-
"""创建考试相关数据库表"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.exam_models import ExamPaper, ExamQuestion, ExamAttempt, ExamAnswer

# 创建所有考试表
Base.metadata.create_all(bind=engine, tables=[
    ExamPaper.__table__,
    ExamQuestion.__table__,
    ExamAttempt.__table__,
    ExamAnswer.__table__,
])
print("考试表创建成功!")

# 验证
import sqlite3
db_path = os.path.join(os.path.dirname(__file__), "app", "static", "qa_database.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'exam_%'")
print("考试表:", [r[0] for r in c.fetchall()])
conn.close()
