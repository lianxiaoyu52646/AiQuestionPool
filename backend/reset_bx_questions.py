"""重置所有试卷的B型和X型题目数据"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.database import SessionLocal
from app.exam_models import ExamPaper, ExamQuestion

db = SessionLocal()

papers = db.query(ExamPaper).order_by(ExamPaper.subject, ExamPaper.year).all()
total_deleted = 0

for p in papers:
    # 删除B型和X型题
    deleted_b = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == p.id,
        ExamQuestion.question_type == 'B'
    ).delete()
    deleted_x = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == p.id,
        ExamQuestion.question_type == 'X'
    ).delete()
    # 也删除C型题（综合分析题，也可能有同样的问题）
    deleted_c = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == p.id,
        ExamQuestion.question_type == 'C'
    ).delete()
    
    total = deleted_b + deleted_x + deleted_c
    total_deleted += total
    remaining = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).count()
    print(f"  ID={p.id} {p.subject} {p.year}: 删除B={deleted_b} X={deleted_x} C={deleted_c} 剩余A型={remaining}")

db.commit()
print(f"\n总共删除: {total_deleted}题")
db.close()
