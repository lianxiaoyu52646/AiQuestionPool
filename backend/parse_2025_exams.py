#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse 2025 exam PDFs and import into database.
Uses the hqwx.com format parser (same as 2024 中药一).
Also crawls 中药综 from hqwx.com web pages (no PDF available).
"""

import sys
import re
import json
import pdfplumber
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.database import SessionLocal
from app.exam_models import ExamPaper, ExamQuestion


def extract_text(pdf_path):
    """Extract all text from PDF, removing headers/footers."""
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text = re.sub(r'咨询热线：400-678-3456[^\n]*', '', text)
                text = re.sub(r'扫码关注人力资源管理公众号[^\n]*', '', text)
                text = re.sub(r'扫码关注执业药师考试公众号[^\n]*', '', text)
                text = re.sub(r'环球网校移动课堂APP[^\n]*', '', text)
                text = re.sub(r'环球网校 侵权必究', '', text)
                text = re.sub(r'免费订阅考试提醒[^\n]*', '', text)
                text = re.sub(r'免费约直播领资料', '', text)
                text = re.sub(r'微信扫码刷题', '', text)
                text = re.sub(r'^-\d+-\s*$', '', text, flags=re.MULTILINE)
                full_text += text + "\n"
    return full_text


def clean_text(text):
    """Clean up text: remove extra whitespace, empty parens."""
    text = re.sub(r'（\s*）', '', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def is_question_start(line):
    """Check if a line starts a new question (N. at start)."""
    m = re.match(r'^(\d+)[\.【]', line.strip())
    if m:
        num = int(m.group(1))
        return num if 1 <= num <= 120 else None
    return None


def is_option_line(line):
    """Check if a line is an option (A. ... B. ... etc)."""
    m = re.match(r'^([A-E])\.\s*(.*)', line.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return None


def is_answer_line(line, hqwx=True):
    """Check if a line contains an answer."""
    if hqwx:
        m = re.search(r'【答案】\s*([A-Z]+(?:[、,][A-Z]+)*)', line)
    else:
        m = re.search(r'答案：([A-Z]+)', line)
    if m:
        return m.group(1)
    return None


# ============================================================
# hqwx.com format parser (2025 中药一, 中药二)
# ============================================================

def parse_hqwx(full_text):
    """Parse hqwx.com format PDF - line by line."""
    lines = full_text.split('\n')
    
    current_section = None
    questions = []
    
    current_group_id = None
    group_shared_options = {}
    group_shared_stem = None
    
    current_q = None
    state = None  # 'stem', 'options', 'group_intro', 'explanation'
    
    for line_raw in lines:
        line = line_raw.strip()
        
        if not line:
            continue
        
        # Skip title/footer lines
        if '2025 年执业药师真题' in line or '真题持续更新' in line or '注意：以上内容' in line:
            continue
        
        # Check for section headers
        if '一、最佳选择题' in line or '一、 最佳选择题' in line:
            current_section = 'A'
            state = None
            continue
        elif '二、配伍选择题' in line or '二、 配伍选择题' in line:
            current_section = 'B'
            state = None
            continue
        elif '三、综合分析题' in line or '三、 综合分析题' in line or '三、综合选择题' in line or '三、 综合选择题' in line:
            current_section = 'C'
            state = None
            continue
        elif '四、多项选择题' in line or '四、 多项选择题' in line:
            current_section = 'X'
            state = None
            continue
        
        # Check for group markers 【N-N】
        group_match = re.search(r'【(\d+-\d+)】', line)
        if group_match:
            if current_q:
                current_q['stem'] = clean_text(current_q['stem'])
                if current_q['question_type'] == 'B' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                elif current_q['question_type'] == 'C' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                questions.append(current_q)
                current_q = None
            
            current_group_id = group_match.group(1)
            group_shared_options = {}
            group_shared_stem = None
            state = 'group_intro'
            
            # Extract shared stem text after the group marker
            extra_text = line[group_match.end():].strip()
            if extra_text and len(extra_text) > 5:
                group_shared_stem = extra_text
            continue
        
        # Check for answer line
        answer = is_answer_line(line, hqwx=True)
        if answer:
            answers = re.split(r'[、,，]', answer)
            
            # Check if the line has a question number prefix (B-type format: "41.【答案】D")
            ans_q_num_match = re.match(r'^(\d+)\.\s*【答案】', line)
            
            if ans_q_num_match:
                # B-type answer with question number prefix
                ans_q_num = int(ans_q_num_match.group(1))
                
                # Find the matching question in the questions list
                target_q = None
                for q in reversed(questions):
                    if q['question_number'] == ans_q_num:
                        target_q = q
                        break
                
                if target_q:
                    # Assign answer to the matched question
                    target_q['answer'] = answers[0].strip()
                    if target_q['question_type'] == 'B' and not target_q['options']:
                        target_q['options'] = group_shared_options.copy()
                    elif target_q['question_type'] == 'B':
                        for k, v in group_shared_options.items():
                            if k not in target_q['options']:
                                target_q['options'][k] = v
                    # Clear current_q if it matches
                    if current_q and current_q['question_number'] == ans_q_num:
                        current_q = None
                elif current_q:
                    # Question not found in list — might be misidentified (e.g., Q61 extracted as Q1)
                    # Assign answer to current_q and fix its question number
                    current_q['answer'] = answers[0].strip()
                    current_q['question_number'] = ans_q_num
                    current_q['stem'] = clean_text(current_q['stem'])
                    if current_q['question_type'] == 'B' and not current_q['options']:
                        current_q['options'] = group_shared_options.copy()
                    elif current_q['question_type'] == 'B':
                        for k, v in group_shared_options.items():
                            if k not in current_q['options']:
                                current_q['options'][k] = v
                    questions.append(current_q)
                    current_q = None
            elif current_q and len(answers) == 1:
                current_q['answer'] = answers[0]
                current_q['stem'] = clean_text(current_q['stem'])
                if current_q['question_type'] == 'B' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                elif current_q['question_type'] == 'B':
                    for k, v in group_shared_options.items():
                        if k not in current_q['options']:
                            current_q['options'][k] = v
                if current_q['question_type'] == 'C' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                questions.append(current_q)
                current_q = None
            elif len(answers) > 1:
                if current_q:
                    current_q['stem'] = clean_text(current_q['stem'])
                    if current_q['question_type'] == 'B' and not current_q['options']:
                        current_q['options'] = group_shared_options.copy()
                    questions.append(current_q)
                    current_q = None
                
                group_id_str = str(current_group_id) if current_group_id else ''
                group_qs = [q for q in questions if (q.get('group_id') or '').endswith(group_id_str) and not q.get('answer')]
                
                if len(group_qs) >= len(answers):
                    for i, ans in enumerate(answers):
                        group_qs[i]['answer'] = ans.strip()
                else:
                    for i, ans in enumerate(answers):
                        if len(group_qs) > i:
                            group_qs[i]['answer'] = ans.strip()
            else:
                if current_q:
                    current_q['stem'] = clean_text(current_q['stem'])
                    if current_q['question_type'] == 'B' and not current_q['options']:
                        current_q['options'] = group_shared_options.copy()
                    questions.append(current_q)
                    current_q = None
            state = None
            continue
        
        # Check for question start
        q_num = is_question_start(line)
        if q_num is not None and current_section:
            if current_q:
                current_q['stem'] = clean_text(current_q['stem'])
                if current_q['question_type'] == 'B' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                questions.append(current_q)
            
            stem_text = re.sub(r'^\d+\.', '', line).strip()
            current_q = {
                'question_number': q_num,
                'question_type': current_section,
                'stem': stem_text,
                'options': {},
                'answer': '',
                'explanation': '',
                'group_id': f'{current_section}-{current_group_id}' if current_group_id else None,
                'shared_stem': group_shared_stem if current_section in ('B', 'C') and group_shared_stem else None
            }
            state = 'stem'
            continue
        
        # Check for option line
        opt = is_option_line(line)
        if opt:
            if state == 'group_intro':
                group_shared_options[opt[0]] = opt[1]
            elif current_q is not None:
                current_q['options'][opt[0]] = opt[1]
                state = 'options'
            continue
        
        # Check for bare E option (no "E." prefix, after D. option)
        # This happens in hqwx.com PDFs where E option text appears without "E." prefix
        if state == 'group_intro' and len(group_shared_options) == 4 and 'E' not in group_shared_options:
            if not line.startswith('【') and not re.match(r'^\d+\.', line):
                group_shared_options['E'] = line
                continue
        elif state == 'options' and current_q is not None and len(current_q['options']) == 4 and 'E' not in current_q['options']:
            if not line.startswith('【') and not re.match(r'^\d+\.', line):
                current_q['options']['E'] = line
                continue
        
        # Non-special line
        if state == 'group_intro':
            if not group_shared_stem:
                group_shared_stem = line
            else:
                group_shared_stem += ' ' + line
        elif state == 'stem' and current_q is not None:
            current_q['stem'] += ' ' + line
        elif state == 'options' and current_q is not None:
            current_q['stem'] += ' ' + line
    
    # Finalize last question
    if current_q:
        current_q['stem'] = clean_text(current_q['stem'])
        if current_q['question_type'] == 'B' and not current_q['options']:
            current_q['options'] = group_shared_options.copy()
        questions.append(current_q)
    
    return questions


# ============================================================
# Import to database
# ============================================================

def import_to_database(questions, subject, year=2025):
    """Import parsed questions into the database."""
    db = SessionLocal()
    
    try:
        existing_paper = db.query(ExamPaper).filter(
            ExamPaper.subject == subject,
            ExamPaper.year == year
        ).first()
        
        if existing_paper:
            db.query(ExamQuestion).filter(
                ExamQuestion.paper_id == existing_paper.id
            ).delete()
            paper = existing_paper
            print(f"Updating existing paper: {paper.id} ({subject} {year})")
        else:
            paper = ExamPaper(
                subject=subject,
                year=year,
                title=f"{year}年执业药师真题《{subject}》",
                description=f"{year}年执业药师考试真题及答案解析",
                total_questions=120,
                time_limit_minutes=120,
                pass_score=72
            )
            db.add(paper)
            db.flush()
            print(f"Created new paper: {paper.id} ({subject} {year})")
        
        questions.sort(key=lambda q: q['question_number'])
        
        imported = 0
        for q in questions:
            if not q['options']:
                print(f"  WARNING: Q{q['question_number']} has no options, skipping")
                continue
            
            clean_opts = {}
            for k, v in q['options'].items():
                clean_opts[k] = v.strip()
            
            db_q = ExamQuestion(
                paper_id=paper.id,
                question_number=q['question_number'],
                question_type=q['question_type'],
                stem=q['stem'],
                options=json.dumps(clean_opts, ensure_ascii=False),
                answer=q['answer'],
                explanation=q.get('explanation', ''),
                group_id=q.get('group_id'),
                shared_stem=q.get('shared_stem')
            )
            db.add(db_q)
            imported += 1
        
        db.commit()
        print(f"Imported {imported} questions for {subject} {year}")
        
        type_counts = {}
        for q in questions:
            type_counts[q['question_type']] = type_counts.get(q['question_type'], 0) + 1
        print(f"  Type breakdown: {type_counts}")
        
        return paper.id
        
    except Exception as e:
        db.rollback()
        print(f"ERROR importing {subject}: {e}")
        raise
    finally:
        db.close()


def main():
    pdfs = [
        {
            'path': r'D:\lian\praPro\e\backend\downloads\2025_pdfs\中药一_2025.pdf',
            'subject': '中药学专业知识一',
            'format': 'hqwx',
        },
        {
            'path': r'D:\lian\praPro\e\backend\downloads\2025_pdfs\中药二_2025.pdf',
            'subject': '中药学专业知识二',
            'format': 'hqwx',
        },
    ]
    
    for pdf_info in pdfs:
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_info['subject']} ({pdf_info['format']} format)")
        print(f"{'='*60}")
        
        full_text = extract_text(pdf_info['path'])
        print(f"Extracted {len(full_text)} characters")
        
        if pdf_info['format'] == 'hqwx':
            questions = parse_hqwx(full_text)
        else:
            questions = parse_hqwx(full_text)
        
        print(f"Parsed {len(questions)} questions")
        
        q_nums = [q['question_number'] for q in questions]
        if q_nums:
            print(f"  Question range: {min(q_nums)} - {max(q_nums)}")
        
        expected = set(range(1, 121))
        actual = set(q_nums)
        missing = expected - actual
        if missing:
            print(f"  WARNING: Missing questions: {sorted(missing)}")
        
        no_opts = [q['question_number'] for q in questions if not q['options']]
        if no_opts:
            print(f"  WARNING: Questions without options: {no_opts}")
        
        no_answer = [q['question_number'] for q in questions if not q['answer']]
        if no_answer:
            print(f"  WARNING: Questions without answer: {no_answer}")
        
        # Print samples
        for q in questions[:3]:
            print(f"\n  Q{q['question_number']} ({q['question_type']}):")
            print(f"    Stem: {q['stem'][:100]}...")
            print(f"    Options: {list(q['options'].keys())}")
            print(f"    Answer: {q['answer']}")
        
        import_to_database(questions, pdf_info['subject'])
    
    print(f"\n{'='*60}")
    print("PDF exams imported successfully!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
