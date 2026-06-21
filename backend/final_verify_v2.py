"""
最终数据质量验证 - 确认所有问题已修复
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
import json

def main():
    db = SessionLocal()
    
    print("=" * 60)
    print("最终数据质量验证")
    print("=" * 60)
    
    # 1. 总览
    papers = db.query(ExamPaper).all()
    total_qs = db.query(ExamQuestion).count()
    print(f"\n📊 总览:")
    print(f"  试卷数: {len(papers)}")
    print(f"  题目总数: {total_qs}")
    
    # 2. 每张试卷的题目数
    print(f"\n📋 各试卷题目数:")
    for p in papers:
        count = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).count()
        status = "✅" if count == 120 else "❌"
        print(f"  {status} Paper {p.id}: {p.title} - {count}题")
    
    # 3. 检查空选项
    print(f"\n🔍 检查空选项:")
    empty_options = 0
    for q in db.query(ExamQuestion).all():
        if not q.options or (isinstance(q.options, dict) and len(q.options) == 0):
            empty_options += 1
            print(f"  ❌ Paper {q.paper_id} Q{q.question_number}: 选项为空")
    if empty_options == 0:
        print(f"  ✅ 所有题目选项完整")
    
    # 4. 检查空解析
    print(f"\n🔍 检查空解析:")
    empty_explanation = 0
    for q in db.query(ExamQuestion).all():
        if not q.explanation or q.explanation.strip() == '':
            empty_explanation += 1
            print(f"  ❌ Paper {q.paper_id} Q{q.question_number}: 解析为空")
    if empty_explanation == 0:
        print(f"  ✅ 所有题目解析完整")
    
    # 5. 检查B/C型题缺少group_id
    print(f"\n🔍 检查B/C型题group_id:")
    bc_no_group = 0
    for q in db.query(ExamQuestion).filter(
        ExamQuestion.question_type.in_(['B', 'C'])
    ).all():
        if not q.group_id:
            bc_no_group += 1
            print(f"  ❌ Paper {q.paper_id} Q{q.question_number} (type={q.question_type}): group_id为空")
    if bc_no_group == 0:
        print(f"  ✅ 所有B/C型题都有group_id")
    
    # 6. 检查空答案
    print(f"\n🔍 检查空答案:")
    empty_answer = 0
    for q in db.query(ExamQuestion).all():
        if not q.answer or q.answer.strip() == '':
            empty_answer += 1
            print(f"  ❌ Paper {q.paper_id} Q{q.question_number}: 答案为空")
    if empty_answer == 0:
        print(f"  ✅ 所有题目答案完整")
    
    # 7. 检查空题干
    print(f"\n🔍 检查空题干:")
    empty_stem = 0
    for q in db.query(ExamQuestion).all():
        if not q.stem or q.stem.strip() == '':
            empty_stem += 1
            print(f"  ❌ Paper {q.paper_id} Q{q.question_number}: 题干为空")
    if empty_stem == 0:
        print(f"  ✅ 所有题目题干完整")
    
    # 总结
    print(f"\n{'='*60}")
    print(f"📊 最终验证结果:")
    print(f"  题目总数: {total_qs}")
    print(f"  空选项: {empty_options}")
    print(f"  空解析: {empty_explanation}")
    print(f"  空答案: {empty_answer}")
    print(f"  空题干: {empty_stem}")
    print(f"  B/C型题缺group_id: {bc_no_group}")
    
    total_issues = empty_options + empty_explanation + empty_answer + empty_stem + bc_no_group
    if total_issues == 0:
        print(f"\n🎉 所有数据质量问题已修复! 0个问题!")
    else:
        print(f"\n⚠️ 仍有 {total_issues} 个问题需要处理")
    
    db.close()

if __name__ == "__main__":
    main()
