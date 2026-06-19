# -*- coding: utf-8 -*-
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "app", "static", "qa_database.db")
print(f"DB path: {db_path}, exists: {os.path.exists(db_path)}, size: {os.path.getsize(db_path) if os.path.exists(db_path) else 0}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"Tables: {tables}")

for t in tables:
    try:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {cnt} rows")
    except Exception as e:
        print(f"  {t}: ERROR {e}")

# 看看 questions 表前几条
if "questions" in tables:
    print("\n--- questions sample ---")
    for row in cur.execute("SELECT id, question_type, substr(question_text,1,40) FROM questions LIMIT 5"):
        print(row)

conn.close()
