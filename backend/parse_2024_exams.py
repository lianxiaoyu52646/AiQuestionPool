#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse 2024 exam PDFs and import into database.
Line-by-line parser for robust extraction.
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
                text = re.sub(r'环球网校移动课堂APP[^\n]*', '', text)
                text = re.sub(r'环球网校 侵权必究', '', text)
                text = re.sub(r'免费订阅考试提醒[^\n]*', '', text)
                text = re.sub(r'免费约直播领资料', '', text)
                text = re.sub(r'微信扫码刷题', '', text)
                text = re.sub(r'官方网站:www\.youlu\.com[^\n]*', '', text)
                text = re.sub(r'【优路教育】', '', text)
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
    # Handle normal "N." and malformed "N【." or "N【." patterns
    m = re.match(r'^(\d+)[\.【]', line.strip())
    if m:
        num = int(m.group(1))
        return num if 1 <= num <= 120 else None
    return None


def is_option_line(line):
    """Check if a line is an option (A. ... B. ... etc)."""
    m = re.match(r'^([A-E])\.(.*)', line.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return None


def is_answer_line(line, hqwx=True):
    """Check if a line contains an answer."""
    if hqwx:
        m = re.search(r'【答案】([A-Z]+(?:、[A-Z]+)*)', line)
    else:
        m = re.search(r'答案：([A-Z]+)', line)
    if m:
        return m.group(1)
    return None


# ============================================================
# hqwx.com format parser (中药一)
# ============================================================

def parse_hqwx(full_text):
    """Parse hqwx.com format PDF (中药一) - line by line."""
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
        if '2024 年执业药师真题' in line or '真题持续更新' in line or '注意：以上内容' in line:
            continue
        
        # Check for section headers
        if '一、最佳选择题' in line:
            current_section = 'A'
            state = None
            continue
        elif '二、配伍选择题' in line:
            current_section = 'B'
            state = None
            continue
        elif '三、案例分析题' in line or '三、综合分析题' in line:
            current_section = 'C'
            state = None
            continue
        elif '四、多项选择题' in line:
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
                questions.append(current_q)
                current_q = None
            
            current_group_id = group_match.group(1)
            group_shared_options = {}
            group_shared_stem = None
            state = 'group_intro'
            continue
        
        # Check for answer line
        answer = is_answer_line(line, hqwx=True)
        if answer:
            # For B-type, answer may be "B、D、E" meaning Q41=B, Q42=D, Q43=E
            answers = re.split(r'[、,，]', answer)
            
            if current_q and len(answers) == 1:
                # Single answer for current question
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
                # Multiple answers for B-type group - assign to recent questions in this group
                # First, append current_q if exists so it's included in the search
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
                    # Fallback: assign to last N questions in this group
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
# youlu.com format parser (中药二/中药综)
# ============================================================

def parse_youlu(full_text):
    """Parse youlu.com format PDF - line by line."""
    lines = full_text.split('\n')
    
    current_section = None
    questions = []
    
    current_group_id = None
    group_shared_options = {}
    group_shared_stem = None
    group_start_num = 0
    
    # Sequential counters for B/C/X-type (don't rely on group markers)
    b_counter = 41
    c_counter = 101  # Will be reset when C-type section starts
    x_counter = 111
    
    current_q = None
    state = None  # 'stem', 'options', 'explanation', 'group_intro'
    explanation_text = ''
    
    for line_raw in lines:
        line = line_raw.strip()
        
        if not line:
            continue
        
        # Skip title/cover lines
        if '2024 年药师考试真题' in line or '优路教育·教学教研中心' in line:
            continue
        if '看真题解析' in line or '考后估分对答案' in line:
            continue
        
        # Check for section headers
        if '大题：单选题' in line:
            current_section = 'A'
            state = None
            continue
        elif '大题：配伍题' in line:
            current_section = 'B'
            state = None
            continue
        elif '大题：材料分析题' in line:
            if current_section != 'C':  # Only reset counter when first entering C-type
                c_counter = b_counter  # C-type starts right after B-type ends
            current_section = 'C'
            state = None
            continue
        elif '大题：多选题' in line:
            current_section = 'X'
            state = None
            continue
        
        # Check for 题目： (new topic in B/C-type)
        if line == '题目：' or line.startswith('题目：'):
            if current_q:
                current_q['stem'] = clean_text(current_q['stem'])
                current_q['explanation'] = clean_text(explanation_text)
                if current_q['question_type'] == 'B' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                questions.append(current_q)
                current_q = None
            
            explanation_text = ''
            group_shared_options = {}
            group_shared_stem = None
            state = 'group_intro'
            continue
        
        # Check for 子题： marker
        if line.startswith('子题：'):
            state = None
            continue
        
        # Check for group info in B-type
        if state == 'group_intro' and current_section == 'B':
            # Match any "根据下面选项...回答" pattern (with or without numbers)
            if '根据下面选项' in line:
                group_info = re.search(r'(\d+)\.\s*根据下面选项.*?回答(\d+-\d+)', line)
                if group_info:
                    current_group_id = group_info.group(2)
                    group_start_num = int(current_group_id.split('-')[0])
                else:
                    # "回答下题" or other variant - just use the number before 根据下面选项
                    m = re.match(r'(\d+)\.', line)
                    current_group_id = m.group(1) if m else 'unknown'
                continue
        
        # Check for background material in C-type
        if state == 'group_intro' and current_section == 'C':
            bg_match = re.search(r'(\d+)\.\s*背景材料：(.*)', line)
            if bg_match:
                current_group_id = bg_match.group(1)
                group_shared_stem = '背景材料：' + bg_match.group(2).strip()
                continue
            elif group_shared_stem:
                group_shared_stem += ' ' + line
                continue
            else:
                bg_match2 = re.match(r'(\d+)\.\s*(.*)', line)
                if bg_match2:
                    current_group_id = bg_match2.group(1)
                    group_shared_stem = bg_match2.group(2).strip()
                    continue
                else:
                    if not group_shared_stem:
                        group_shared_stem = line
                    else:
                        group_shared_stem += ' ' + line
                    continue
        
        # Check for answer line
        answer = is_answer_line(line, hqwx=False)
        if answer:
            if current_q:
                current_q['answer'] = answer
                current_q['stem'] = clean_text(current_q['stem'])
                current_q['explanation'] = clean_text(explanation_text)
                if current_q['question_type'] == 'B' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                questions.append(current_q)
                current_q = None
            explanation_text = ''
            state = 'explanation'
            continue
        
        # Check for question start FIRST (before explanation check)
        # This ensures new questions are detected even during explanation collection
        # But skip lines that are actually group info ("根据下面选项")
        if '根据下面选项' in line or '背景材料' in line:
            q_num = None
        else:
            q_num = is_question_start(line)
        if q_num is not None and current_section:
            if current_q:
                current_q['stem'] = clean_text(current_q['stem'])
                current_q['explanation'] = clean_text(explanation_text)
                if current_q['question_type'] == 'B' and not current_q['options']:
                    current_q['options'] = group_shared_options.copy()
                questions.append(current_q)
            
            explanation_text = ''
            stem_text = re.sub(r'^\d+[\.【]+', '', line).strip()
            # Remove leading 优路教育】 if present
            stem_text = re.sub(r'^.*?】', '', stem_text).strip() if '】' in stem_text[:20] else stem_text
            
            # Determine actual question number using sequential counters
            actual_num = q_num
            if current_section == 'B':
                actual_num = b_counter
                b_counter += 1
            elif current_section == 'C':
                actual_num = c_counter
                c_counter += 1
            elif current_section == 'X':
                actual_num = x_counter
                x_counter += 1
            
            current_q = {
                'question_number': actual_num,
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
        
        # Check for explanation start
        if line.startswith('解析：') or line.startswith('解析:'):
            explanation_text = re.sub(r'^解析[：:]\s*', '', line)
            state = 'explanation'
            continue
        
        # If in explanation state, collect explanation text
        if state == 'explanation':
            explanation_text += ' ' + line
            continue
        
        # Check for option line
        opt = is_option_line(line)
        if opt:
            if state == 'group_intro' and current_section == 'B':
                group_shared_options[opt[0]] = opt[1]
            elif current_q is not None:
                current_q['options'][opt[0]] = opt[1]
                state = 'options'
            continue
        
        # Non-special line
        if state == 'group_intro' and current_section == 'B':
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
        current_q['explanation'] = clean_text(explanation_text)
        if current_q['question_type'] == 'B' and not current_q['options']:
            current_q['options'] = group_shared_options.copy()
        questions.append(current_q)
    
    return questions


# ============================================================
# Import to database
# ============================================================

def import_to_database(questions, subject, year=2024):
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
            'path': r'D:\lian\praPro\e\backend\2024_zhongyao1.pdf',
            'subject': '中药一',
            'format': 'hqwx',
        },
        {
            'path': r'D:\lian\praPro\e\backend\2024_zhongyao2.pdf',
            'subject': '中药二',
            'format': 'youlu',
        },
        {
            'path': r'D:\lian\praPro\e\backend\2024_zhongyaozong.pdf',
            'subject': '中药综',
            'format': 'youlu',
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
            questions = parse_youlu(full_text)
        
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
    print("All 2024 exam PDFs imported successfully!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
