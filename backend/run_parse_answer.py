# -*- coding: utf-8 -*-
"""直接运行答案PDF解析脚本（不通过FastAPI后台任务）
解析答案PDF，将答案和解析匹配到已有的题目上。
"""
import sys
import os
import asyncio
import sqlite3

# Ensure CWD is the backend directory (database_url is relative)
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models import PDFFile, Question, Category
from app.routers.pdf import _do_parse_answer_pdf


async def main():
    db = SessionLocal()
    try:
        # Find the answer PDF (pdf_id=2, linked_pdf_id=1)
        pdf = db.query(PDFFile).filter(PDFFile.id == 2).first()
        if not pdf:
            print("Answer PDF (id=2) not found")
            return
        print(f"Starting answer parse: {pdf.filename} ({pdf.total_pages} pages)")
        print(f"Linked to question PDF: {pdf.linked_pdf_id}")

        # Check how many questions need answers
        linked_id = pdf.linked_pdf_id
        total_q = db.query(Question).filter(Question.pdf_id == linked_id).count()
        answered_q = db.query(Question).filter(
            Question.pdf_id == linked_id,
            Question.answer != "",
            Question.answer != None
        ).count()
        print(f"Questions: {total_q} total, {answered_q} already have answers, {total_q - answered_q} need answers")

        pdf.parse_status = "parsing"
        pdf.parse_progress = 0
        pdf.parse_error = ""
        db.commit()

        await _do_parse_answer_pdf(db, pdf)

        # Final stats
        answered_after = db.query(Question).filter(
            Question.pdf_id == linked_id,
            Question.answer != "",
            Question.answer != None
        ).count()
        print(f"Done! status={pdf.parse_status} progress={pdf.parse_progress} matched={pdf.parsed_questions}")
        print(f"Questions with answers: {answered_after}/{total_q}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        pdf = db.query(PDFFile).filter(PDFFile.id == 2).first()
        if pdf:
            pdf.parse_status = "failed"
            pdf.parse_error = str(e)[:500]
            db.commit()
        print(f"FAILED: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
