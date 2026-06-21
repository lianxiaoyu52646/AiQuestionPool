"""最终数据质量验证脚本"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal

db = SessionLocal()

# 1. 检查所有试卷的题目数量
print('=' * 60)
print('1. 试卷题目数量检查')
print('=' * 60)
papers = db.query(ExamPaper).order_by(ExamPaper.id).all()
total_q = 0
for p in papers:
    count = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).count()
    status = '✅' if count == 120 else '❌'
    print(f'{status} Paper {p.id}: {p.subject} {p.year} - {count}题')
    total_q += count
print(f'总计: {total_q} 题')

# 2. 检查B/C型题选项是否为空
print()
print('=' * 60)
print('2. B/C型题选项为空检查')
print('=' * 60)
empty_options = db.query(ExamQuestion).filter(
    ExamQuestion.question_type.in_(['B', 'C']),
    ExamQuestion.options == '{}'
).all()
if empty_options:
    for q in empty_options:
        p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
        print(f'❌ Paper {p.id} ({p.year}): Q{q.question_number} ({q.question_type}型) 选项为空')
else:
    print('✅ 所有B/C型题选项均已填充')

# 3. 检查X型题答案是否多字母
print()
print('=' * 60)
print('3. X型题答案长度检查')
print('=' * 60)
x_questions = db.query(ExamQuestion).filter(ExamQuestion.question_type == 'X').all()
short_answers = []
for q in x_questions:
    ans = q.answer.strip() if q.answer else ''
    if len(ans) < 2:
        p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
        short_answers.append(f'❌ Paper {p.id} ({p.year}): Q{q.question_number} 答案="{q.answer}"')
if short_answers:
    for s in short_answers:
        print(s)
else:
    print(f'✅ 所有{len(x_questions)}道X型题答案均为多字母')

# 4. 检查B/C型题的group_id和shared_stem
print()
print('=' * 60)
print('4. B/C型题 group_id 和 shared_stem 检查')
print('=' * 60)
bc_questions = db.query(ExamQuestion).filter(ExamQuestion.question_type.in_(['B', 'C'])).all()
no_group = [q for q in bc_questions if not q.group_id]
no_stem = [q for q in bc_questions if not q.shared_stem]
print(f'B/C型题总数: {len(bc_questions)}')
print(f'有group_id: {len(bc_questions) - len(no_group)}, 缺失: {len(no_group)}')
print(f'有shared_stem: {len(bc_questions) - len(no_stem)}, 缺失: {len(no_stem)}')
if no_group:
    for q in no_group[:5]:
        p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
        print(f'  ⚠️ Paper {p.id} ({p.year}): Q{q.question_number} 无group_id')
if no_stem:
    for q in no_stem[:5]:
        p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
        print(f'  ⚠️ Paper {p.id} ({p.year}): Q{q.question_number} 无shared_stem')

# 5. 检查答案为空的题目
print()
print('=' * 60)
print('5. 答案/解析为空检查')
print('=' * 60)
no_answer = db.query(ExamQuestion).filter(
    (ExamQuestion.answer == None) | (ExamQuestion.answer == '')
).all()
no_explain = db.query(ExamQuestion).filter(
    (ExamQuestion.explanation == None) | (ExamQuestion.explanation == '')
).all()
print(f'答案为空: {len(no_answer)} 题')
print(f'解析为空: {len(no_explain)} 题')
if no_answer:
    for q in no_answer[:10]:
        p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
        print(f'  ❌ Paper {p.id} ({p.year}): Q{q.question_number} ({q.question_type}型) 答案为空')

# 6. 检查A型题选项为空的题目
print()
print('=' * 60)
print('6. A型题选项为空检查')
print('=' * 60)
a_empty = db.query(ExamQuestion).filter(
    ExamQuestion.question_type == 'A',
    ExamQuestion.options == '{}'
).all()
if a_empty:
    for q in a_empty:
        p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
        stem_preview = q.stem[:60] if q.stem else '(无题干)'
        print(f'  ⚠️ Paper {p.id} ({p.year}): Q{q.question_number} (A型) 选项为空 - {stem_preview}...')
else:
    print('✅ 所有A型题选项均已填充')

# 7. 按题型统计
print()
print('=' * 60)
print('7. 题型分布统计')
print('=' * 60)
for p in papers:
    types = {}
    qs = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).all()
    for q in qs:
        types[q.question_type] = types.get(q.question_type, 0) + 1
    type_str = ', '.join([f'{k}型{v}题' for k, v in sorted(types.items())])
    print(f'Paper {p.id} ({p.year}): {type_str}')

db.close()
print()
print('=' * 60)
print('数据质量验证完成!')
print('=' * 60)
