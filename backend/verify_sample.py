# -*- coding: utf-8 -*-
"""抽样检查题目内容和答案对应关系"""
import sqlite3
import json

db = sqlite3.connect('app/static/qa_database.db')
cur = db.cursor()

# 抽样检查：每套试卷第1题
print('=== 各试卷第1题抽样 ===')
for pid in range(1, 13):
    cur.execute('SELECT question_number, question_type, stem, options, answer, explanation FROM exam_questions WHERE paper_id=? AND question_number=1', (pid,))
    r = cur.fetchone()
    opts = json.loads(r[3]) if r[3] else {}
    opt_keys = list(opts.keys())
    stem_preview = r[2][:60] if r[2] else ''
    correct_opt = opts.get(r[4], '?')[:30] if r[4] else ''
    print(f'  试卷{pid} 第1题 [{r[1]}型] 答案={r[4]}')
    print(f'    题干: {stem_preview}...')
    print(f'    选项: {opt_keys}')
    print(f'    正确选项内容: {correct_opt}')
    print(f'    解析: {r[5][:50] if r[5] else ""}...')
    print()

# 检查X型题
print('=== X型题抽样(每套试卷) ===')
for pid in range(1, 13):
    cur.execute('SELECT question_number, stem, answer, explanation FROM exam_questions WHERE paper_id=? AND question_type="X" LIMIT 1', (pid,))
    r = cur.fetchone()
    if r:
        print(f'  试卷{pid} 第{r[0]}题: 答案={r[2]}, 题干: {r[1][:50]}...')

# 检查B型题
print()
print('=== B型题抽样(试卷1) ===')
cur.execute('SELECT question_number, stem, shared_stem, answer FROM exam_questions WHERE paper_id=1 AND question_type="B" LIMIT 5')
for r in cur.fetchall():
    ss = r[2][:40] if r[2] else ''
    print(f'  第{r[0]}题: 答案={r[3]}, 共用题干: {ss}...')

# 检查C型题
print()
print('=== C型题抽样(试卷1) ===')
cur.execute('SELECT question_number, stem, shared_stem, answer FROM exam_questions WHERE paper_id=1 AND question_type="C" LIMIT 5')
for r in cur.fetchall():
    ss = r[2][:40] if r[2] else ''
    print(f'  第{r[0]}题: 答案={r[3]}, 共用题干: {ss}...')

db.close()
print('\n✅ 抽样检查完成')
