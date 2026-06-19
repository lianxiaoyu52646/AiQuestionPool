# -*- coding: utf-8 -*-
"""直接运行题目PDF解析脚本（不通过FastAPI后台任务）"""
import sys
import os
import asyncio

# Ensure CWD is the backend directory (database_url is relative)
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models import PDFFile, Question, Category
from app.routers.pdf import _do_parse_question_pdf


async def main():
    db = SessionLocal()
    try:
        pdf = db.query(PDFFile).filter(PDFFile.id == 1).first()
        if not pdf:
            print("PDF id=1 not found")
            return
        print(f"Starting parse: {pdf.filename} ({pdf.total_pages} pages)")

        # 断点续传：不清空已有数据，保留已完成的chunk结果
        # 只重置状态为parsing，进度保持上次值
        if pdf.parse_status != "completed":
            pdf.parse_status = "parsing"
            pdf.parse_error = ""
            db.commit()
        await _do_parse_question_pdf(db, pdf)
        print(f"Done! status={pdf.parse_status} progress={pdf.parse_progress} questions={pdf.parsed_questions}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        pdf = db.query(PDFFile).filter(PDFFile.id == 1).first()
        if pdf:
            pdf.parse_status = "failed"
            pdf.parse_error = str(e)[:500]
            db.commit()
        print(f"FAILED: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
