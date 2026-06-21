"""调查数据质量问题"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
import json

db = SessionLocal()

# 1. 调查 Paper 7 Q55/Q56 选项为空
print('=' * 60)
print('1. Paper 7 (专一2021) Q55/Q56 选项为空调查')
print('=' * 60)
for qn in [55, 56]:
    q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 7, ExamQuestion.question_number == qn).first()
    if q:
        print(f'\nQ{qn} ({q.question_type}型):')
        print(f'  stem: {q.stem[:100] if q.stem else "(空)"}...')
        print(f'  shared_stem: {q.shared_stem[:100] if q.shared_stem else "(空)"}')
        print(f'  options: {q.options}')
        print(f'  answer: {q.answer}')
        print(f'  group_id: {q.group_id}')
        print(f'  explanation: {q.explanation[:100] if q.explanation else "(空)"}...')

# 2. 调查缺失group_id的B/C型题
print()
print('=' * 60)
print('2. 缺失group_id的B/C型题分布')
print('=' * 60)
no_group_qs = db.query(ExamQuestion).filter(
    ExamQuestion.question_type.in_(['B', 'C']),
    ExamQuestion.group_id == None
).all()
# 按paper_id分组
from collections import defaultdict
by_paper = defaultdict(list)
for q in no_group_qs:
    by_paper[q.paper_id].append(q.question_number)

for pid in sorted(by_paper.keys()):
    p = db.query(ExamPaper).filter(ExamPaper.id == pid).first()
    qns = by_paper[pid]
    print(f'Paper {pid} ({p.subject} {p.year}): {len(qns)}题缺失 - 题号: {qns[:20]}{"..." if len(qns) > 20 else ""}')

# 3. 看看有group_id的B/C型题的shared_stem样例
print()
print('=' * 60)
print('3. 有group_id的B/C型题shared_stem样例 (Paper 8)')
print('=' * 60)
sample = db.query(ExamQuestion).filter(
    ExamQuestion.paper_id == 8,
    ExamQuestion.question_type == 'B',
    ExamQuestion.group_id != None
).first()
if sample:
    print(f'Q{sample.question_number}: group_id={sample.group_id}')
    print(f'  shared_stem: {sample.shared_stem[:200] if sample.shared_stem else "(空)"}')
    print(f'  options: {json.dumps(sample.options, ensure_ascii=False)[:200]}')

# 4. 看看缺失group_id的B/C型题的shared_stem
print()
print('=' * 60)
print('4. 缺失group_id的B/C型题shared_stem样例')
print('=' * 60)
no_group_sample = db.query(ExamQuestion).filter(
    ExamQuestion.paper_id == 8,
    ExamQuestion.question_type == 'B',
    ExamQuestion.group_id == None
).first()
if no_group_sample:
    print(f'Q{no_group_sample.question_number}: group_id={no_group_sample.group_id}')
    print(f'  shared_stem: "{no_group_sample.shared_stem}"')
    print(f'  stem: {no_group_sample.stem[:100] if no_group_sample.stem else "(空)"}...')
    print(f'  options: {json.dumps(no_group_sample.options, ensure_ascii=False)[:200]}')

# 5. 调查解析为空的题目
print()
print('=' * 60)
print('5. 解析为空的题目')
print('=' * 60)
no_explain = db.query(ExamQuestion).filter(
    (ExamQuestion.explanation == None) | (ExamQuestion.explanation == '')
).all()
for q in no_explain:
    p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
    print(f'Paper {p.id} ({p.year}): Q{q.question_number} ({q.question_type}型)')
    print(f'  stem: {q.stem[:80] if q.stem else "(空)"}...')
    print(f'  answer: {q.answer}')

# 6. 调查 Paper 5 Q37/Q39/Q40 选项为空
print()
print('=' * 60)
print('6. Paper 5 (专一2023) Q37/Q39/Q40 选项为空调查')
print('=' * 60)
for qn in [37, 39, 40]:
    q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 5, ExamQuestion.question_number == qn).first()
    if q:
        print(f'\nQ{qn} ({q.question_type}型):')
        print(f'  stem: {q.stem[:120] if q.stem else "(空)"}...')
        print(f'  options: {q.options}')
        print(f'  answer: {q.answer}')
        print(f'  explanation: {q.explanation[:100] if q.explanation else "(空)"}...')

db.close()
