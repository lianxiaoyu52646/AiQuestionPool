# -*- coding: utf-8 -*-
"""检查考试题目和答案数据"""
import sqlite3
import json

conn = sqlite3.connect('app/static/qa_database.db')
c = conn.cursor()

# 检查试卷详情
c.execute('SELECT * FROM exam_papers')
print('=== 试卷 ===')
for r in c.fetchall():
    print(f'id={r[0]}, subject={r[1]}, year={r[2]}, title={r[3]}, total_q={r[5]}, time={r[6]}min, pass={r[7]}')

# 检查题目：前10题
c.execute('SELECT id, paper_id, question_number, question_type, stem, options, answer, explanation, group_id, shared_stem FROM exam_questions ORDER BY question_number LIMIT 10')
print('\n=== 前10题 ===')
for r in c.fetchall():
    opts = json.loads(r[5]) if r[5] else {}
    opt_keys = list(opts.keys())
    print(f'  Q{r[2]} [{r[3]}] answer={r[6]} opts={opt_keys} group={r[8]} stem={r[4][:80]}...')

# 统计题目类型分布
c.execute('SELECT question_type, COUNT(*) FROM exam_questions GROUP BY question_type')
print('\n=== 题型分布 ===')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}题')

# 检查答案为空的题目
c.execute("SELECT COUNT(*) FROM exam_questions WHERE answer IS NULL OR answer = ''")
print(f'\n答案为空的题目: {c.fetchone()[0]}')

# 检查答案长度分布
c.execute('SELECT answer, COUNT(*) FROM exam_questions GROUP BY answer ORDER BY COUNT(*) DESC LIMIT 20')
print('\n=== 答案分布(前20) ===')
for r in c.fetchall():
    print(f'  answer={r[0]}: {r[1]}题')

# 检查options为空的题目
c.execute("SELECT question_number, options FROM exam_questions WHERE options IS NULL OR options = '' OR options = '{}'")
print(f'\n=== options为空的题目 ===')
empty_opts = c.fetchall()
print(f'共 {len(empty_opts)} 题')
for r in empty_opts[:5]:
    print(f'  Q{r[0]}')

# 检查B型题的分组
c.execute("SELECT group_id, COUNT(*) FROM exam_questions WHERE question_type = 'B' GROUP BY group_id ORDER BY group_id")
print('\n=== B型题分组 ===')
for r in c.fetchall():
    print(f'  group={r[0]}: {r[1]}题')

# 检查C型题的分组
c.execute("SELECT group_id, COUNT(*) FROM exam_questions WHERE question_type = 'C' GROUP BY group_id ORDER BY group_id")
print('\n=== C型题分组 ===')
for r in c.fetchall():
    print(f'  group={r[0]}: {r[1]}题')

# 检查X型题答案
c.execute("SELECT question_number, answer FROM exam_questions WHERE question_type = 'X' ORDER BY question_number")
print('\n=== X型题答案 ===')
for r in c.fetchall():
    print(f'  Q{r[0]}: {r[1]}')

# 检查考试记录
c.execute('SELECT id, paper_id, score, correct_count, wrong_count, unanswered, total_answered, time_used_seconds, status FROM exam_attempts ORDER BY id')
print('\n=== 考试记录 ===')
for r in c.fetchall():
    print(f'  attempt={r[0]} paper={r[1]} score={r[2]} correct={r[3]} wrong={r[4]} unanswered={r[5]} answered={r[6]} time={r[7]}s status={r[8]}')

# 检查答题记录中is_correct为NULL的情况
c.execute("SELECT COUNT(*) FROM exam_answers WHERE is_correct IS NULL")
print(f'\n答题记录中is_correct为NULL: {c.fetchone()[0]}')

# 检查答题记录总数
c.execute("SELECT COUNT(*) FROM exam_answers")
print(f'答题记录总数: {c.fetchone()[0]}')

conn.close()
