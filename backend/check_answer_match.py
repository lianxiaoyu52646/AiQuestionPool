# -*- coding: utf-8 -*-
"""对比 all_answers.json 和 exam_questions 的答案是否匹配"""
import sqlite3
import json

# 加载 all_answers.json
with open('all_answers.json', 'r', encoding='utf-8') as f:
    all_answers = json.load(f)

print(f'all_answers.json 总答案数: {len(all_answers)}')
print(f'all_answers.json 前5题:')
for a in all_answers[:5]:
    print(f'  Q{a["question_number"]} [{a["question_type"]}] answer={a["answer"]} chapter={a["chapter"][:20]}...')

# 加载数据库 exam_questions
conn = sqlite3.connect('app/static/qa_database.db')
c = conn.cursor()
c.execute('SELECT question_number, question_type, stem, answer, explanation FROM exam_questions ORDER BY question_number')
db_questions = c.fetchall()
print(f'\nexam_questions 总题数: {len(db_questions)}')
print(f'exam_questions 前5题:')
for q in db_questions[:5]:
    print(f'  Q{q[0]} [{q[1]}] answer={q[3]} stem={q[2][:60]}...')

# 对比前10题的答案
print('\n=== 前10题答案对比 ===')
print(f'{"题号":<6} {"DB答案":<10} {"JSON答案":<10} {"匹配":<6}')
for i in range(min(10, len(db_questions), len(all_answers))):
    db_q = db_questions[i]
    json_a = all_answers[i]
    match = "✓" if db_q[3] == json_a["answer"] else "✗"
    print(f'Q{db_q[0]:<5} {db_q[3]:<10} {json_a["answer"]:<10} {match}')

# 检查 all_answers.json 的题号分布
print('\n=== all_answers.json 题号范围 ===')
nums = [int(a["question_number"]) for a in all_answers if a["question_number"].isdigit()]
print(f'  题号范围: {min(nums)} - {max(nums)}')
print(f'  总数: {len(nums)}')

# 检查 all_answers.json 的章节分布
chapters = set()
for a in all_answers:
    chapters.add(a.get("chapter", ""))
print(f'\n  章节数: {len(chapters)}')
for ch in sorted(chapters)[:10]:
    count = sum(1 for a in all_answers if a.get("chapter") == ch)
    print(f'    {ch[:40]}: {count}题')

# 检查 exam_questions 的题干是否包含章节信息
print('\n=== exam_questions 题干样本 ===')
for q in db_questions[:3]:
    print(f'  Q{q[0]}: {q[2][:100]}')
    print(f'    explanation: {q[4][:100] if q[4] else "无"}')

conn.close()
