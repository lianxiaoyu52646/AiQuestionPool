# -*- coding: utf-8 -*-
"""检查答题记录中is_correct为NULL的问题"""
import sqlite3

conn = sqlite3.connect('app/static/qa_database.db')
c = conn.cursor()

# 检查is_correct为NULL的答题记录
c.execute('SELECT attempt_id, question_id, user_answer, is_correct FROM exam_answers WHERE is_correct IS NULL LIMIT 20')
print('=== is_correct为NULL的答题记录(前20) ===')
for r in c.fetchall():
    print(f'  attempt={r[0]} q={r[1]} user_ans={r[2]} is_correct={r[3]}')

# 检查is_correct为NULL但user_answer不为空的记录
c.execute("SELECT COUNT(*) FROM exam_answers WHERE is_correct IS NULL AND user_answer != ''")
print(f'\nis_correct为NULL但user_answer不为空: {c.fetchone()[0]}')

# 检查is_correct为NULL且user_answer为空的记录
c.execute("SELECT COUNT(*) FROM exam_answers WHERE is_correct IS NULL AND user_answer = ''")
print(f'is_correct为NULL且user_answer为空: {c.fetchone()[0]}')

# 检查attempt 5的答题详情
c.execute('SELECT question_id, user_answer, is_correct FROM exam_answers WHERE attempt_id = 5')
print('\n=== attempt 5 答题详情 ===')
for r in c.fetchall():
    print(f'  q={r[0]} ans={r[1]} correct={r[2]}')

# 检查attempt 2的答题详情（10题全对的那次）
c.execute('SELECT question_id, user_answer, is_correct FROM exam_answers WHERE attempt_id = 2 AND user_answer != ""')
print('\n=== attempt 2 已答题目 ===')
for r in c.fetchall():
    print(f'  q={r[0]} ans={r[1]} correct={r[2]}')

conn.close()
