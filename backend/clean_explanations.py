"""
清理Q4/Q6的解析内容，去除广告和无关文本
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
import re

def clean_explanation(text):
    """清理解析文本"""
    if not text:
        return text
    
    # 去除"举一反三"及之后的内容
    text = re.sub(r'举一反三.*$', '', text, flags=re.DOTALL)
    # 去除"V2会员专享"及之后的内容
    text = re.sub(r'V2会员专享.*$', '', text, flags=re.DOTALL)
    # 去除"开始练 习"及之后的内容
    text = re.sub(r'开始练\s*习.*$', '', text, flags=re.DOTALL)
    # 去除"当前可体验"及之后的内容
    text = re.sub(r'当前可体验.*$', '', text, flags=re.DOTALL)
    # 去除"根据错题"及之后的内容
    text = re.sub(r'根据错题.*$', '', text, flags=re.DOTALL)
    
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def main():
    db = SessionLocal()
    
    for qn in [4, 6]:
        q = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == 1,
            ExamQuestion.question_number == qn
        ).first()
        
        if not q:
            continue
        
        print(f"Q{qn}:")
        print(f"  原始解析: {q.explanation[:200]}...")
        
        cleaned = clean_explanation(q.explanation)
        print(f"  清理后: {cleaned[:200]}...")
        
        if cleaned != q.explanation:
            q.explanation = cleaned
            db.commit()
            print(f"  ✅ 已更新")
        else:
            print(f"  无需清理")
        print()
    
    db.close()
    print("完成!")

if __name__ == "__main__":
    main()
