"""重置受影响试卷的数据"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.database import SessionLocal
from app.exam_models import ExamPaper, ExamQuestion

db = SessionLocal()

# 查看所有试卷
papers = db.query(ExamPaper).order_by(ExamPaper.subject, ExamPaper.year).all()
print("当前试卷列表:")
for p in papers:
    q_count = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).count()
    b_count = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == p.id,
        ExamQuestion.question_type == 'B'
    ).count()
    x_count = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == p.id,
        ExamQuestion.question_type == 'X'
    ).count()
    print(f"  ID={p.id} {p.subject} {p.year} 总题数={q_count} B型={b_count} X型={x_count}")

db.close()
