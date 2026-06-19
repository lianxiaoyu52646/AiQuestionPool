# -*- coding: utf-8 -*-
"""Run parallel agent-based question parsing.

Usage: python run_agent_parse.py [pdf_id] [num_workers]

Features:
- Multi-agent parallel: N workers process chunks simultaneously
- ReAct pattern: each worker thinks → acts → observes → retries if needed
- Memory compression: auto-compresses old messages when token threshold exceeded
- Breakpoint resume: all state in DB, re-run continues from where it left off
"""
import os
import sys
import json
import time

backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models import PDFFile, Question, Category
from app.services.agent_service import TaskCoordinator


def load_ocr_cache(pdf_id: int) -> list:
    """Load OCR cache chunks for a PDF."""
    cache_path = os.path.join("app", "static", "uploads", f".ocr_cache_{pdf_id}.json")
    if not os.path.exists(cache_path):
        print(f"ERROR: OCR cache not found at {cache_path}")
        print("Please run OCR first (upload PDF and trigger parse).")
        sys.exit(1)
    
    with open(cache_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    print(f"OCR cache loaded: {len(chunks)} chunks")
    return chunks


def build_cat_map(pdf_id: int) -> dict:
    """Build category mapping for a PDF."""
    db = SessionLocal()
    categories = db.query(Category).filter(Category.pdf_id == pdf_id).order_by(Category.order_index).all()
    cat_map = {f"cat_{c.order_index}": c.id for c in categories}
    db.close()
    print(f"Categories: {len(categories)}")
    return cat_map


def main():
    pdf_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    num_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    
    print(f"=== Agent-Based Parallel Parser ===")
    print(f"PDF ID: {pdf_id}")
    print(f"Workers: {num_workers}")
    print()
    
    # Load OCR cache
    chunks = load_ocr_cache(pdf_id)
    
    # Build category map
    cat_map = build_cat_map(pdf_id)
    
    # Check current state
    db = SessionLocal()
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if not pdf:
        print(f"ERROR: PDF with id={pdf_id} not found")
        sys.exit(1)
    
    current_questions = db.query(Question).filter(Question.pdf_id == pdf_id).count()
    print(f"PDF: {pdf.filename} ({pdf.total_pages} pages)")
    print(f"Current status: {pdf.parse_status}, questions: {current_questions}")
    print()
    
    # Reset PDF status
    pdf.parse_status = "parsing"
    pdf.parse_error = ""
    db.commit()
    db.close()
    
    # Run parallel parsing
    start_time = time.time()
    coordinator = TaskCoordinator(num_workers=num_workers)
    result = coordinator.run_parse(
        pdf_id=pdf_id,
        chunks=chunks,
        cat_map=cat_map,
        task_type="parse_questions"
    )
    elapsed = time.time() - start_time
    
    print()
    print(f"=== Results ===")
    print(f"Session ID: {result['session_id']}")
    print(f"Status: {result['status']}")
    print(f"Chunks: {result['done_chunks']}/{result['total_chunks']} done, {result['failed_chunks']} failed")
    print(f"Total questions: {result['total_questions']}")
    print(f"Memory compressed: {result['memory_compressed']} times")
    print(f"Total tokens used: {result['total_tokens']}")
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    
    # Update PDF status
    db = SessionLocal()
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if result["status"] == "completed":
        pdf.parse_status = "completed"
        pdf.parse_progress = 100
    elif result["status"] == "paused":
        pdf.parse_status = "partial"
        pdf.parse_progress = int(result["done_chunks"] / result["total_chunks"] * 100)
    else:
        pdf.parse_status = "failed"
    pdf.parsed_questions = result["total_questions"]
    db.commit()
    db.close()
    
    db2 = SessionLocal()
    pdf2 = db2.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    print(f"\nPDF status updated: {pdf2.parse_status}")
    db2.close()


if __name__ == "__main__":
    main()
