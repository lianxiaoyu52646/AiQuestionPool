# -*- coding: utf-8 -*-
"""PDF upload and management routes"""
import os
import shutil
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import PDFFile, Category, Question, UserProgress, ReviewLog, question_tags
from app.services.pdf_service import PDFService
from app.services.kimi_service import KimiService
from app.services.fsrs_service import FSRSService
from app.services.answer_parser import parse_answer_pdf
from app.config import get_settings


def _match_category(db: Session, pdf_id: int, page_number: int, cat_map: dict) -> int | None:
    """Match a question to a category based on page number.
    Falls back to the first category if no match found.
    """
    if not cat_map:
        return None
    categories = db.query(Category).filter(Category.pdf_id == pdf_id).order_by(Category.order_index).all()
    if not categories:
        return list(cat_map.values())[0]
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if not pdf or pdf.total_pages == 0:
        return categories[0].id
    pages_per_cat = max(1, pdf.total_pages // len(categories))
    cat_index = min(page_number // pages_per_cat, len(categories) - 1)
    return categories[cat_index].id

router = APIRouter(prefix="/api/pdf", tags=["PDF"])
pdf_service = PDFService()
kimi_service = KimiService()
fsrs_service = FSRSService()
settings = get_settings()


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    pdf_type: str = Form("combined"),
    linked_pdf_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload PDF file and create record.
    pdf_type: 'question' (题目PDF, scanned), 'answer' (答案PDF, text), 'combined' (题答合一)
    linked_pdf_id: when uploading an answer PDF, link it to the question PDF
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    if len(content) > settings.max_file_size:
        raise HTTPException(400, "File exceeds 50MB limit")

    file_path = pdf_service.save_upload(file.filename, content)
    info = pdf_service.get_file_info(file_path)

    pdf_record = PDFFile(
        filename=file.filename,
        file_path=file_path,
        total_pages=info["page_count"],
        pdf_type=pdf_type,
        linked_pdf_id=linked_pdf_id
    )
    db.add(pdf_record)
    db.commit()
    db.refresh(pdf_record)

    return {
        "id": pdf_record.id,
        "filename": pdf_record.filename,
        "total_pages": pdf_record.total_pages,
        "pdf_type": pdf_record.pdf_type,
        "is_scanned": info.get("is_scanned", False),
        "message": "Upload successful, please call /api/pdf/{id}/parse to start parsing"
    }


@router.post("/{pdf_id}/parse")
async def parse_pdf(pdf_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start async PDF parsing. Returns immediately, client polls /parse-status."""
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if not pdf:
        raise HTTPException(404, "PDF not found")

    if pdf.parse_status == "parsing":
        raise HTTPException(400, "Already parsing")

    pdf.parse_status = "parsing"
    pdf.parse_progress = 0
    pdf.parsed_questions = 0
    pdf.parse_error = ""
    db.commit()

    background_tasks.add_task(_do_parse, pdf_id)

    return {"message": "Parsing started", "pdf_id": pdf_id}


async def _do_parse(pdf_id: int):
    """Background parsing task - runs outside request context."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
        if not pdf:
            return

        # Route to the correct parsing strategy based on pdf_type
        if pdf.pdf_type == "answer":
            await _do_parse_answer_pdf(db, pdf)
        elif pdf.pdf_type == "question":
            await _do_parse_question_pdf(db, pdf)
        else:
            await _do_parse_combined_pdf(db, pdf)

    except Exception as e:
        pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
        if pdf:
            pdf.parse_status = "failed"
            pdf.parse_error = str(e)
            db.commit()
    finally:
        db.close()


async def _do_parse_question_pdf(db, pdf: PDFFile):
    """Parse a question-only PDF (typically scanned, needs OCR).
    Extracts questions with chapter/section/question_type/question_number but no answers.
    Uses chunked OCR (extract_text_by_pages) to avoid timeout on large scanned PDFs.

    Resume support:
    - OCR results are cached incrementally per-chunk (.ocr_cache_{id}.json).
    - Kimi extraction progress is tracked per-chunk (.parse_progress_{id}.json).
    - On restart, completed OCR chunks and extraction chunks are skipped.
    """
    import json as _json
    import os as _os

    cache_dir = _os.path.dirname(pdf.file_path)
    ocr_cache_path = _os.path.join(cache_dir, f".ocr_cache_{pdf.id}.json")
    progress_path = _os.path.join(cache_dir, f".parse_progress_{pdf.id}.json")

    # --- Phase 1: OCR (full-document single pass, then split into chunks) ---
    import fitz as _fitz
    doc = _fitz.open(pdf.file_path)
    total_pages = len(doc)
    doc.close()

    chunk_size = 5
    total_chunks = (total_pages + chunk_size - 1) // chunk_size

    # Load OCR cache if available
    if _os.path.exists(ocr_cache_path):
        with open(ocr_cache_path, "r", encoding="utf-8") as f:
            chunks = _json.load(f)
        if len(chunks) == total_chunks and all(c for c in chunks):
            print(f"OCR cache complete: {total_chunks} chunks loaded", flush=True)
        else:
            print(f"OCR cache incomplete ({sum(1 for c in chunks if c)}/{total_chunks}), re-OCR needed", flush=True)
            chunks = None

    if not chunks:
        # Run MinerU ONCE on the entire PDF (much faster than per-chunk)
        is_scanned = pdf_service._is_scanned_pdf(pdf.file_path)
        if is_scanned:
            print(f"Running full-document MinerU OCR on {total_pages} pages...", flush=True)
            import tempfile as _tempfile
            import shutil as _shutil
            output_dir = _tempfile.mkdtemp(prefix="mineru_full_")

            venv_python = __import__("sys").executable
            venv_scripts = _os.path.dirname(venv_python)
            mineru_exe = _os.path.join(venv_scripts, "mineru.exe")
            if not _os.path.exists(mineru_exe):
                mineru_exe = _os.path.join(venv_scripts, "mineru")

            cmd = [
                mineru_exe, "-p", pdf.file_path, "-o", output_dir,
                "-m", "ocr", "-b", "pipeline", "-l", "ch",
                "-f", "false", "-t", "false",
            ]
            import subprocess as _subprocess
            result = _subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=1800, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                print(f"MinerU failed: {result.stderr[-500:]}", flush=True)
                pdf.parse_status = "failed"
                pdf.parse_error = f"MinerU OCR failed: {result.stderr[-200:]}"
                db.commit()
                _shutil.rmtree(output_dir, ignore_errors=True)
                return

            # Parse content_list.json (has page_idx for each item)
            content_list_path = None
            for root, dirs, files in _os.walk(output_dir):
                for f in files:
                    if f.endswith("_content_list.json"):
                        content_list_path = _os.path.join(root, f)
                        break

            if not content_list_path:
                # Fallback: use .md file
                md_text = ""
                for root, dirs, files in _os.walk(output_dir):
                    for f in files:
                        if f.endswith(".md"):
                            with open(_os.path.join(root, f), "r", encoding="utf-8") as mf:
                                md_text += mf.read() + "\n"
                # Single chunk with all text
                chunks = [{"start_page": 1, "end_page": total_pages, "text": md_text}]
            else:
                with open(content_list_path, "r", encoding="utf-8") as f:
                    content_data = _json.load(f)

                # Group by page_idx
                pages_dict = {}
                for item in content_data:
                    pidx = item.get("page_idx", 0)
                    if pidx not in pages_dict:
                        pages_dict[pidx] = []
                    text = item.get("text", "")
                    if text:
                        pages_dict[pidx].append(text)

                # Build chunks
                chunks = []
                for i in range(0, total_pages, chunk_size):
                    start_page = i + 1
                    end_page = min(i + chunk_size, total_pages)
                    texts = []
                    for p in range(i, end_page):
                        if p in pages_dict:
                            texts.append(f"--- Page {p+1} ---\n" + "\n".join(pages_dict[p]))
                    chunk_text = "\n\n".join(texts) if texts else ""
                    chunks.append({
                        "start_page": start_page,
                        "end_page": end_page,
                        "text": chunk_text
                    })

            _shutil.rmtree(output_dir, ignore_errors=True)
            print(f"MinerU OCR done: {len(chunks)} chunks, total {sum(len(c['text']) for c in chunks)} chars", flush=True)
        else:
            # Text PDF: use PyMuPDF directly
            d = _fitz.open(pdf.file_path)
            chunks = []
            for i in range(0, total_pages, chunk_size):
                chunk_text = ""
                start_page = i + 1
                end_page = min(i + chunk_size, total_pages)
                for pn in range(i, end_page):
                    chunk_text += f"\n--- Page {pn+1} ---\n{d[pn].get_text()}"
                chunks.append({"start_page": start_page, "end_page": end_page, "text": chunk_text})
            d.close()

        # Save cache
        with open(ocr_cache_path, "w", encoding="utf-8") as f:
            _json.dump(chunks, f, ensure_ascii=False)
        print(f"Cached {len(chunks)} chunks to {ocr_cache_path}", flush=True)

    total_chunks = len(chunks)

    # --- Phase 2: Load extraction progress ---
    if _os.path.exists(progress_path):
        with open(progress_path, "r", encoding="utf-8") as f:
            prog = _json.load(f)
        done_chunks = set(prog.get("done_chunks", []))
        print(f"Loaded extraction progress: {len(done_chunks)} chunks already extracted")
    else:
        done_chunks = set()

    # --- Phase 3: Categories (only if not yet created) ---
    existing_cats = db.query(Category).filter(Category.pdf_id == pdf.id).all()
    if existing_cats:
        cat_map = {c.name: c.id for c in existing_cats}
        print(f"Reusing {len(existing_cats)} existing categories")
    else:
        first_text = ""
        for c in chunks:
            if c and c.get("text", "").strip() and "[OCR failed]" not in c["text"]:
                first_text = c["text"]
                break

        categories = await kimi_service.extract_categories(first_text[:3000])
        cat_map = {}
        if categories:
            for cat in categories:
                category = Category(
                    name=cat.get("name", "Uncategorized"),
                    pdf_id=pdf.id,
                    order_index=cat.get("order_index", 0)
                )
                db.add(category)
                db.commit()
                db.refresh(category)
                cat_map[category.name] = category.id
        else:
            category = Category(name="Default Category", pdf_id=pdf.id, order_index=0)
            db.add(category)
            db.commit()
            db.refresh(category)
            cat_map["Default Category"] = category.id

    # --- Phase 4: Kimi extraction per chunk (skip already-done) ---
    total_questions = db.query(Question).filter(Question.pdf_id == pdf.id).count()

    for i, chunk in enumerate(chunks):
        if i in done_chunks:
            pdf.parse_progress = int((i + 1) / total_chunks * 100)
            pdf.parsed_questions = total_questions
            db.commit()
            continue

        chunk_text = chunk.get("text", "") if chunk else ""
        if not chunk_text.strip() or "[OCR failed]" in chunk_text:
            done_chunks.add(i)
            prog = {"done_chunks": sorted(done_chunks)}
            with open(progress_path, "w", encoding="utf-8") as f:
                _json.dump(prog, f, ensure_ascii=False)
            pdf.parse_progress = int((i + 1) / total_chunks * 100)
            db.commit()
            continue

        print(f"  Extracting chunk {i+1}/{total_chunks} (pages {chunk['start_page']}-{chunk['end_page']})...", flush=True)
        try:
            questions = await kimi_service.extract_questions(chunk_text)
        except Exception as e:
            err_detail = f"{type(e).__name__}: {e}"
            import traceback
            tb = traceback.format_exc()
            print(f"    Kimi extraction failed for chunk {i+1}: {err_detail}", flush=True)
            print(f"    Traceback: {tb[:500]}", flush=True)
            # Don't mark as done, so it retries next time
            pdf.parse_progress = int((i + 1) / total_chunks * 100)
            pdf.parse_error = f"Chunk {i+1} failed: {str(e)[:100]}"
            db.commit()
            continue

        # If extraction returned 0 questions, check if text actually has questions
        if not questions:
            # Check if the chunk text looks like it contains questions
            has_question_markers = any(marker in chunk_text for marker in [
                "选择题", "正确的是", "错误的是", "不属于", "属于", "是指", "特点是",
                "配伍", "共用备选", "综合分析", "多项选择"
            ])
            if has_question_markers:
                # Text has question markers but extraction returned 0 — API failure
                print(f"    -> 0 questions but text has question markers, NOT marking done (will retry)", flush=True)
                pdf.parse_progress = int((i + 1) / total_chunks * 100)
                pdf.parse_error = f"Chunk {i+1}: extraction returned 0 but text has questions"
                db.commit()
                continue
            else:
                print(f"    -> 0 questions (text has no parseable questions), marking done", flush=True)
                done_chunks.add(i)
                prog = {"done_chunks": sorted(done_chunks)}
                with open(progress_path, "w", encoding="utf-8") as f:
                    _json.dump(prog, f, ensure_ascii=False)
                pdf.parse_progress = int((i + 1) / total_chunks * 100)
                db.commit()
                continue

        for q in questions:
            existing = db.query(Question).filter(
                Question.pdf_id == pdf.id,
                Question.question_text == q["question_text"]
            ).first()
            if existing:
                continue

            category_id = _match_category(db, pdf.id, chunk["start_page"], cat_map)

            question = Question(
                pdf_id=pdf.id,
                category_id=category_id,
                question_text=q["question_text"],
                options=q.get("options", []),
                answer="",
                explanation="",
                question_type=q.get("question_type", "single"),
                page_number=chunk["start_page"],
                difficulty=q.get("difficulty", 3),
                question_number=q.get("question_number", ""),
                chapter=q.get("chapter", ""),
                section=q.get("section", "")
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            total_questions += 1

        # Mark this chunk as done
        done_chunks.add(i)
        prog = {"done_chunks": sorted(done_chunks)}
        with open(progress_path, "w", encoding="utf-8") as f:
            _json.dump(prog, f, ensure_ascii=False)

        pdf.parse_progress = int((i + 1) / total_chunks * 100)
        pdf.parsed_questions = total_questions
        db.commit()
        print(f"    -> {len(questions)} questions, total now {total_questions}", flush=True)

    # --- Phase 5: Check if all chunks are done ---
    if len(done_chunks) == total_chunks:
        pdf.parse_status = "completed"
        pdf.parse_progress = 100
        pdf.parsed_questions = total_questions
        db.commit()
        print(f"All {total_chunks} chunks completed! Total questions: {total_questions}", flush=True)
        # Clean up progress file
        if _os.path.exists(progress_path):
            _os.remove(progress_path)
    else:
        pdf.parse_status = "partial"
        pdf.parse_progress = int(len(done_chunks) / total_chunks * 100)
        pdf.parsed_questions = total_questions
        pdf.parse_error = f"{len(done_chunks)}/{total_chunks} chunks completed, {total_chunks - len(done_chunks)} remaining"
        db.commit()
        print(f"Partial: {len(done_chunks)}/{total_chunks} chunks done, {total_questions} questions", flush=True)


async def _do_parse_answer_pdf(db, pdf: PDFFile):
    """Parse an answer-only PDF and match answers to existing questions.

    Uses the regex-based `answer_parser` (no AI, fast & accurate for text PDFs).
    Matching key (in priority order):
      1. chapter + section + question_type + question_number
      2. chapter + question_type + question_number  (section may differ in OCR)
      3. question_type + question_number  (global fallback within linked PDF)
      4. sequential order within (chapter, section, question_type) bucket
    """
    if not pdf.linked_pdf_id:
        pdf.parse_status = "failed"
        pdf.parse_error = "Answer PDF has no linked question PDF (linked_pdf_id is null)"
        db.commit()
        return

    linked_pdf = db.query(PDFFile).filter(PDFFile.id == pdf.linked_pdf_id).first()
    if not linked_pdf:
        pdf.parse_status = "failed"
        pdf.parse_error = f"Linked question PDF {pdf.linked_pdf_id} not found"
        db.commit()
        return

    # Parse answers via regex (fast, no AI needed for text-based answer PDF)
    try:
        answers = parse_answer_pdf(pdf.file_path)
    except Exception as e:
        pdf.parse_status = "failed"
        pdf.parse_error = f"Answer parsing failed: {e}"
        db.commit()
        return

    if not answers:
        pdf.parse_status = "failed"
        pdf.parse_error = "No answers could be extracted from answer PDF"
        db.commit()
        return

    # Pre-load all questions of the linked PDF, grouped for fast lookup
    all_questions = db.query(Question).filter(Question.pdf_id == linked_pdf.id).all()

    # Build lookup indexes
    by_full_key = {}      # (chapter, section, qtype, qnum) -> Question
    by_chap_type = {}     # (chapter, qtype, qnum) -> Question
    by_type_num = {}      # (qtype, qnum) -> Question
    by_chap_sec_type = {}  # (chapter, section, qtype) -> [Question...] ordered

    for q in all_questions:
        qn = (q.chapter or "").strip()
        qs = (q.section or "").strip()
        qt = (q.question_type or "single").strip()
        qnum = (q.question_number or "").strip()
        by_full_key[(qn, qs, qt, qnum)] = q
        by_chap_type[(qn, qt, qnum)] = q
        by_type_num[(qt, qnum)] = q
        by_chap_sec_type.setdefault((qn, qs, qt), []).append(q)

    matched_ids = set()
    matched_count = 0
    total = len(answers)

    # Track per-bucket sequential index for fallback #4
    bucket_seq_idx = {}  # (chapter, section, qtype) -> next index

    for i, ans in enumerate(answers):
        a_chap = (ans.get("chapter") or "").strip()
        a_sec = (ans.get("section") or "").strip()
        a_type = (ans.get("question_type") or "single").strip()
        a_num = (ans.get("question_number") or "").strip()
        a_ans = ans.get("answer", "")
        a_exp = ans.get("explanation", "")

        question = None

        # 1. Full key match
        if not question:
            question = by_full_key.get((a_chap, a_sec, a_type, a_num))

        # 2. chapter + type + number (section may differ between OCR and answer PDF)
        if not question:
            question = by_chap_type.get((a_chap, a_type, a_num))

        # 3. type + number (global)
        if not question:
            question = by_type_num.get((a_type, a_num))

        # 4. Sequential order within bucket
        if not question:
            bucket_key = (a_chap, a_sec, a_type)
            bucket = by_chap_sec_type.get(bucket_key) or by_chap_sec_type.get((a_chap, "", a_type))
            if bucket:
                idx = bucket_seq_idx.get(bucket_key, 0)
                if idx < len(bucket):
                    question = bucket[idx]
                    bucket_seq_idx[bucket_key] = idx + 1

        if question and question.id not in matched_ids:
            question.answer = a_ans
            question.explanation = a_exp
            matched_ids.add(question.id)
            matched_count += 1

        # Update progress every 50 items
        if i % 50 == 0 or i == total - 1:
            pdf.parse_progress = int((i + 1) / total * 100)
            pdf.parsed_questions = matched_count
            db.commit()

    pdf.parse_status = "completed"
    pdf.parse_progress = 100
    pdf.parsed_questions = matched_count
    db.commit()


async def _do_parse_combined_pdf(db, pdf: PDFFile):
    """Parse a combined PDF (questions + answers together) - legacy mode."""
    text, _ = pdf_service.extract_text(pdf.file_path)

    categories = await kimi_service.extract_categories(text[:3000])
    cat_map = {}
    if categories:
        for cat in categories:
            category = Category(
                name=cat.get("name", "Uncategorized"),
                pdf_id=pdf.id,
                order_index=cat.get("order_index", 0)
            )
            db.add(category)
            db.commit()
            db.refresh(category)
            cat_map[category.name] = category.id
    else:
        category = Category(name="Default Category", pdf_id=pdf.id, order_index=0)
        db.add(category)
        db.commit()
        db.refresh(category)
        cat_map["Default Category"] = category.id

    chunks = pdf_service.extract_text_by_pages(pdf.file_path, chunk_size=5)
    total_chunks = len(chunks)
    total_questions = 0

    for i, chunk in enumerate(chunks):
        questions = await kimi_service.extract_combined(chunk["text"])

        for q in questions:
            existing = db.query(Question).filter(
                Question.pdf_id == pdf.id,
                Question.question_text == q["question_text"]
            ).first()
            if existing:
                continue

            category_id = _match_category(db, pdf.id, chunk["start_page"], cat_map)

            question = Question(
                pdf_id=pdf.id,
                category_id=category_id,
                question_text=q["question_text"],
                options=q.get("options", []),
                answer=q.get("answer", ""),
                explanation=q.get("explanation", ""),
                question_type=q.get("question_type", "single"),
                page_number=chunk["start_page"],
                difficulty=q.get("difficulty", 3),
                question_number=q.get("question_number", ""),
                chapter=q.get("chapter", ""),
                section=q.get("section", "")
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            total_questions += 1

        pdf.parse_progress = int((i + 1) / total_chunks * 100)
        pdf.parsed_questions = total_questions
        db.commit()

    pdf.parse_status = "completed"
    pdf.parse_progress = 100
    pdf.parsed_questions = total_questions
    db.commit()


@router.get("/{pdf_id}/parse-status")
def get_parse_status(pdf_id: int, db: Session = Depends(get_db)):
    """Poll parsing progress"""
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if not pdf:
        raise HTTPException(404, "PDF not found")

    return {
        "status": pdf.parse_status or "pending",
        "progress": pdf.parse_progress or 0,
        "parsed_questions": pdf.parsed_questions or 0,
        "error": pdf.parse_error or ""
    }


@router.get("/list")
def list_pdfs(db: Session = Depends(get_db)):
    """Get PDF list"""
    pdfs = db.query(PDFFile).order_by(PDFFile.upload_time.desc()).all()
    return [
        {
            "id": p.id,
            "filename": p.filename,
            "total_pages": p.total_pages,
            "upload_time": p.upload_time.isoformat() if p.upload_time else None,
            "question_count": len(p.questions),
            "parse_status": p.parse_status or "pending",
            "parse_progress": p.parse_progress or 0,
            "parsed_questions": p.parsed_questions or 0,
            "pdf_type": p.pdf_type or "combined",
            "linked_pdf_id": p.linked_pdf_id
        }
        for p in pdfs
    ]


@router.get("/{pdf_id}/file")
def get_pdf_file(pdf_id: int, db: Session = Depends(get_db)):
    """Get PDF file for preview"""
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if not pdf:
        raise HTTPException(404, "PDF not found")

    return FileResponse(pdf.file_path, media_type="application/pdf")


@router.delete("/{pdf_id}")
def delete_pdf(pdf_id: int, db: Session = Depends(get_db)):
    """Delete PDF and all associated data (questions, progress, logs, tags, categories)"""
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if not pdf:
        raise HTTPException(404, "PDF not found")

    # Delete file
    if os.path.exists(pdf.file_path):
        os.remove(pdf.file_path)

    # Explicitly delete associated data to avoid orphaned records
    question_ids = [q.id for q in pdf.questions]
    if question_ids:
        # Delete review logs
        db.query(ReviewLog).filter(ReviewLog.question_id.in_(question_ids)).delete(synchronize_session=False)
        # Delete user progress
        db.query(UserProgress).filter(UserProgress.question_id.in_(question_ids)).delete(synchronize_session=False)
        # Clear tag associations
        db.execute(question_tags.delete().where(question_tags.c.question_id.in_(question_ids)))
        # Delete questions
        db.query(Question).filter(Question.id.in_(question_ids)).delete(synchronize_session=False)

    # Delete categories
    db.query(Category).filter(Category.pdf_id == pdf_id).delete(synchronize_session=False)

    # Delete PDF record
    db.delete(pdf)
    db.commit()

    return {"message": "Deleted successfully"}
