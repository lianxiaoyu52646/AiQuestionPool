# -*- coding: utf-8 -*-
"""检查数据库中考试表的状态"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "app", "static", "qa_database.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("所有表:", tables)

for t in ["exam_papers", "exam_questions", "exam_attempts", "exam_answers"]:
    if t in tables:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"{t}: {c.fetchone()[0]} 条记录")
    else:
        print(f"{t}: 表不存在")

# 如果有数据，看看有哪些试卷
if "exam_papers" in tables:
    c.execute("SELECT id, subject, year, title FROM exam_papers ORDER BY id")
    for row in c.fetchall():
        print(f"  试卷: id={row[0]}, subject={row[1]}, year={row[2]}, title={row[3]}")

conn.close()
