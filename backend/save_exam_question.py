# -*- coding: utf-8 -*-
"""
爬虫辅助脚本 - 接收从浏览器提取的题目JSON数据，存入数据库
用法: python save_exam_question.py '{"question_number":1,"question_type":"A","stem":"...","options":{...},"answer":"E","explanation":"..."}'
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.exam_models import ExamPaper, ExamQuestion


def save_question(paper_id, data):
    """保存单题到数据库"""
    db = SessionLocal()
    try:
        # 清理题干中的标签文本
        stem = data.get('stem', '')
        # 移除"过期考点争议题"等标签
        for tag in ['过期考点争议题', '争议题', '过期考点']:
            stem = stem.replace(tag, '').strip()
        
        q_num = data.get('question_number', 0)
        
        # 检查是否已存在
        existing = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == paper_id,
            ExamQuestion.question_number == q_num
        ).first()
        
        if existing:
            existing.question_type = data.get('question_type', 'A')
            existing.stem = stem
            existing.options = data.get('options', {})
            existing.answer = data.get('answer', '')
            existing.explanation = data.get('explanation', '')
        else:
            q = ExamQuestion(
                paper_id=paper_id,
                question_number=q_num,
                question_type=data.get('question_type', 'A'),
                stem=stem,
                options=data.get('options', {}),
                answer=data.get('answer', ''),
                explanation=data.get('explanation', ''),
                shared_stem=data.get('shared_stem')
            )
            db.add(q)
        
        db.commit()
        print(f"[OK] 已保存第{q_num}题 [{data.get('question_type','A')}] 答案:{data.get('answer','')}")
        return True
    except Exception as e:
        print(f"[FAIL] 保存失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_progress(paper_id):
    """获取爬取进度"""
    db = SessionLocal()
    try:
        total = db.query(ExamQuestion).filter(ExamQuestion.paper_id == paper_id).count()
        return total
    finally:
        db.close()


def get_crawled_numbers(paper_id):
    """获取已爬取的题号列表"""
    db = SessionLocal()
    try:
        rows = db.query(ExamQuestion.question_number).filter(
            ExamQuestion.paper_id == paper_id
        ).order_by(ExamQuestion.question_number).all()
        return [r[0] for r in rows]
    finally:
        db.close()


def ensure_paper(subject, year, title):
    """确保试卷记录存在"""
    db = SessionLocal()
    try:
        paper = db.query(ExamPaper).filter(
            ExamPaper.subject == subject,
            ExamPaper.year == year
        ).first()
        if not paper:
            paper = ExamPaper(
                subject=subject,
                year=year,
                title=title,
                description=f"{year}年执业药师{subject}真题",
                total_questions=120,
                time_limit_minutes=120,
                pass_score=72
            )
            db.add(paper)
            db.commit()
            db.refresh(paper)
            print(f"✅ 创建试卷: {title} (id={paper.id})")
        return paper.id
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python save_exam_question.py <command> [args]")
        print("  python save_exam_question.py progress <paper_id>")
        print("  python save_exam_question.py numbers <paper_id>")
        print("  python save_exam_question.py ensure <subject> <year> <title>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "progress":
        pid = int(sys.argv[2])
        print(get_progress(pid))
    elif cmd == "numbers":
        pid = int(sys.argv[2])
        print(json.dumps(get_crawled_numbers(pid)))
    elif cmd == "ensure":
        subject = sys.argv[2]
        year = int(sys.argv[3])
        title = sys.argv[4]
        pid = ensure_paper(subject, year, title)
        print(f"paper_id={pid}")
    elif cmd == "save":
        paper_id = int(sys.argv[2])
        data = json.loads(sys.argv[3])
        save_question(paper_id, data)
    elif cmd == "list":
        db = SessionLocal()
        try:
            papers = db.query(ExamPaper).order_by(ExamPaper.subject, ExamPaper.year).all()
            for p in papers:
                count = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).count()
                print(f"  [{p.id}] {p.subject} {p.year} ({count}/{p.total_questions}) {p.title}")
        finally:
            db.close()
