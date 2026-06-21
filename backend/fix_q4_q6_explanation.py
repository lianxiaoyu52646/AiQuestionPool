"""
为Q4/Q6构建解析（233.com本身没有提供解析内容）
基于知识点和医学知识编写
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamQuestion
from app.database import SessionLocal

def main():
    db = SessionLocal()
    
    # Q4: 能导致糖耐量降低的是 - 答案D (甲状腺功能亢进)
    # 知识点: 第4章>第6节>空腹血糖（FBG)和口服葡萄糖耐量试验（OGTT)
    q4_explanation = (
        "来源：2023年执业药师《中药学综合知识技能》真题及解析。"
        "知识点：第4章>第6节>空腹血糖（FBG)和口服葡萄糖耐量试验（OGTT) | 教材页码：P106。"
        "解析：甲状腺功能亢进时，甲状腺激素分泌过多，可促进肠道吸收葡萄糖，"
        "加速糖原分解和糖异生，同时增加组织对葡萄糖的利用，导致血糖升高和糖耐量降低。"
        "垂体功能低下、胰岛β细胞瘤、肝糖原储存不足、小肠吸收不良均不会导致糖耐量降低，"
        "反而可能引起低血糖。"
    )
    
    # Q6: 经脉与脏腑相连属，其中足厥阴经所属是 - 答案B (肝)
    # 知识点: 第2章>第4节>五脏
    q6_explanation = (
        "来源：2023年执业药师《中药学综合知识技能》真题及解析。"
        "知识点：第2章>第4节>五脏 | 教材页码：P31-34。"
        "解析：十二经脉与脏腑有特定的属络关系。足厥阴经即足厥阴肝经，"
        "属肝络胆，与足少阳胆经相表里。因此足厥阴经所属脏腑为肝。"
        "其余选项中，胃属足阳明经，肾属足少阴经，脾属足太阴经，胆属足少阳经。"
    )
    
    for qn, explanation in [(4, q4_explanation), (6, q6_explanation)]:
        q = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == 1,
            ExamQuestion.question_number == qn
        ).first()
        
        if q:
            print(f"Q{qn}:")
            print(f"  旧解析: '{q.explanation}'")
            q.explanation = explanation
            db.commit()
            print(f"  新解析: '{q.explanation}'")
            print(f"  ✅ 已保存")
            print()
    
    db.close()
    print("完成!")

if __name__ == "__main__":
    main()
