"""深入调查所有待修复问题的细节"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
import json

db = SessionLocal()

# 1. Paper 5 Q37/Q39/Q40 - 从解析中提取选项的可能性
print('=' * 70)
print('1. Paper 5 (专一2023) Q37/Q39/Q40 - 图片题解析内容')
print('=' * 70)
for qn in [37, 39, 40]:
    q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 5, ExamQuestion.question_number == qn).first()
    if q:
        print(f'\nQ{qn} ({q.question_type}型):')
        print(f'  stem: {q.stem}')
        print(f'  answer: {q.answer}')
        print(f'  explanation: {q.explanation}')
        print()

# 2. Paper 7 Q55/Q56 - 从解析中提取选项
print('=' * 70)
print('2. Paper 7 (专一2021) Q55/Q56 - 完整内容')
print('=' * 70)
for qn in [53, 54, 55, 56, 57]:
    q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 7, ExamQuestion.question_number == qn).first()
    if q:
        print(f'\nQ{qn} ({q.question_type}型):')
        print(f'  stem: {q.stem}')
        print(f'  options: {json.dumps(q.options, ensure_ascii=False)}')
        print(f'  answer: {q.answer}')
        print(f'  shared_stem: "{q.shared_stem}"')
        print(f'  group_id: {q.group_id}')
        print(f'  explanation: {q.explanation}')
        print()

# 3. Paper 1 Q4/Q6 - 解析为空
print('=' * 70)
print('3. Paper 1 (综合2023) Q4/Q6 - 完整内容')
print('=' * 70)
for qn in [3, 4, 5, 6, 7]:
    q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 1, ExamQuestion.question_number == qn).first()
    if q:
        print(f'\nQ{qn} ({q.question_type}型):')
        print(f'  stem: {q.stem[:80]}...' if q.stem and len(q.stem) > 80 else f'  stem: {q.stem}')
        print(f'  options: {json.dumps(q.options, ensure_ascii=False)[:200]}')
        print(f'  answer: {q.answer}')
        print(f'  explanation: "{q.explanation}"')
        print()

# 4. 检查有group_id的B型题模式 - 看看group_id是如何分配的
print('=' * 70)
print('4. 有group_id的B/C型题模式 (Paper 8 专一2020)')
print('=' * 70)
qs = db.query(ExamQuestion).filter(
    ExamQuestion.paper_id == 8,
    ExamQuestion.question_type.in_(['B', 'C'])
).order_by(ExamQuestion.question_number).all()
for q in qs:
    print(f'Q{q.question_number} ({q.question_type}型): group_id={q.group_id}, shared_stem="{q.shared_stem[:60] if q.shared_stem and q.shared_stem != "None" else "(空)"}"')

# 5. 检查Paper 2 (综合2022) 的B型题模式 - 缺失group_id的
print()
print('=' * 70)
print('5. Paper 2 (综合2022) B/C型题模式 - 缺失group_id')
print('=' * 70)
qs = db.query(ExamQuestion).filter(
    ExamQuestion.paper_id == 2,
    ExamQuestion.question_type.in_(['B', 'C'])
).order_by(ExamQuestion.question_number).all()
for q in qs[:20]:
    opts = q.options if isinstance(q.options, str) else json.dumps(q.options, ensure_ascii=False)
    print(f'Q{q.question_number} ({q.question_type}型): group_id={q.group_id}, shared_stem="{q.shared_stem}", options_len={len(opts)}')

# 6. 看看Paper 2 Q41-50的stem，判断是否共用选项
print()
print('=' * 70)
print('6. Paper 2 Q41-50 题干内容 (判断分组)')
print('=' * 70)
for qn in range(41, 51):
    q = db.query(ExamQuestion).filter(ExamQuestion.paper_id == 2, ExamQuestion.question_number == qn).first()
    if q:
        opts = q.options if isinstance(q.options, str) else json.dumps(q.options, ensure_ascii=False)
        print(f'Q{qn}: stem="{q.stem[:60]}..." options={opts[:80]}...')

db.close()
