"""检查缺失group_id题目的选项情况"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
import json

db = SessionLocal()

# 检查所有缺失group_id的B/C型题的选项是否为空
print('=' * 60)
print('缺失group_id的B/C型题选项情况')
print('=' * 60)

no_group_qs = db.query(ExamQuestion).filter(
    ExamQuestion.question_type.in_(['B', 'C']),
    ExamQuestion.group_id == None
).all()

has_options = 0
no_options = 0
for q in no_group_qs:
    if q.options and q.options != '{}':
        has_options += 1
    else:
        no_options += 1

print(f'缺失group_id的B/C型题总数: {len(no_group_qs)}')
print(f'  有选项: {has_options}')
print(f'  无选项: {no_options}')

# 看几个样例
print()
print('样例 (Paper 8 Q101):')
q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 8, ExamQuestion.question_number == 101).first()
if q:
    print(f'  type: {q.question_type}')
    print(f'  stem: {q.stem[:100] if q.stem else "(空)"}...')
    print(f'  options: {json.dumps(q.options, ensure_ascii=False)}')
    print(f'  answer: {q.answer}')
    print(f'  shared_stem: "{q.shared_stem}"')
    print(f'  group_id: {q.group_id}')
    print(f'  explanation: {q.explanation[:100] if q.explanation else "(空)"}...')

print()
print('样例 (Paper 2 Q41):')
q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 2, ExamQuestion.question_number == 41).first()
if q:
    print(f'  type: {q.question_type}')
    print(f'  stem: {q.stem[:100] if q.stem else "(空)"}...')
    print(f'  options: {json.dumps(q.options, ensure_ascii=False)}')
    print(f'  answer: {q.answer}')
    print(f'  shared_stem: "{q.shared_stem}"')
    print(f'  group_id: {q.group_id}')
    print(f'  explanation: {q.explanation[:100] if q.explanation else "(空)"}...')

print()
print('样例 (Paper 2 Q91):')
q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 2, ExamQuestion.question_number == 91).first()
if q:
    print(f'  type: {q.question_type}')
    print(f'  stem: {q.stem[:100] if q.stem else "(空)"}...')
    print(f'  options: {json.dumps(q.options, ensure_ascii=False)}')
    print(f'  answer: {q.answer}')
    print(f'  shared_stem: "{q.shared_stem}"')
    print(f'  group_id: {q.group_id}')
    print(f'  explanation: {q.explanation[:100] if q.explanation else "(空)"}...')

# 检查Paper 2的B型题Q41-Q90是否有选项
print()
print('=' * 60)
print('Paper 2 (综合2022) Q41-Q110 选项检查')
print('=' * 60)
for qn in range(41, 111):
    q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 2, ExamQuestion.question_number == qn).first()
    if q:
        opts = q.options if isinstance(q.options, str) else json.dumps(q.options, ensure_ascii=False)
        has_opt = opts and opts != '{}'
        print(f'Q{qn} ({q.question_type}型): options={"有" if has_opt else "空"}, shared_stem={"有" if q.shared_stem else "空"}, group_id={q.group_id}')

db.close()
