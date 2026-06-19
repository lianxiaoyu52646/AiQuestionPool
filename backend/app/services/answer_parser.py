# -*- coding: utf-8 -*-
"""Answer PDF parser - regex-based extraction for text-based answer PDFs.

Designed for the "1200题中药学综合 答案与解析.pdf" structure:
  部分 -> 章 -> 节 -> 题型 -> 题目条目

Entry format:
  N.解析：
  【N】本题考查...故本题答案为C。
  答案：C

Group (配伍) format:
  N.解析：
  【N～M】本组题考查...①...故本题答案为E。②...故本题答案为E。
  答案：EE      # each char maps to N, N+1, ..., M
"""
import re
import fitz  # PyMuPDF
from typing import List, Dict, Any

# Type label -> question_type code stored in DB
TYPE_MAP = {
    "单项选择题": "single",
    "多项选择题": "multiple",
    "配伍选择题": "matching",
    "综合分析题": "comprehensive",
}

# Regex patterns
RE_CHAPTER = re.compile(r'(?m)^(第[一二三四五六七八九十百]+章[^\n]{0,30})$')
RE_SECTION = re.compile(r'(?m)^(第[一二三四五六七八九十百]+节[^\n]{0,30})$')
RE_TYPE = re.compile(r'(?m)^(单项选择题|多项选择题|配伍选择题|综合分析题)$')
# Entry start: "1.解析" or "1.解析：" (number followed by .．、 then 解析)
RE_ENTRY = re.compile(r'(?m)^(\d+)[.．、]\s*解析')
# Answer line: "答案：C" or "答案：AB"
RE_ANSWER = re.compile(r'答案[：:]\s*([A-Za-z]+)')
# Group marker: 【21～22】 or 【3~4】 or 【5-6】
RE_GROUP = re.compile(r'【(\d+)\s*[～~-]\s*(\d+)】')


def _norm(text: str) -> str:
    """Normalize whitespace for matching keys."""
    return re.sub(r'\s+', '', text).strip()


def parse_answer_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Parse a text-based answer PDF into a list of answer dicts.

    Each dict:
      {
        "question_number": "1",
        "chapter": "第一章执业药师与中药药学服务",
        "section": "第一节 中药药学服务及其模式",
        "question_type": "single",  # single/multiple/matching/comprehensive
        "answer": "C",
        "explanation": "本题考查..."
      }

    For 配伍 groups (【N～M】), one entry per question number is produced,
    with the group answer string split char-by-char (e.g. "EE" -> N:E, N+1:E).
    """
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    # State trackers
    current_chapter = ""
    current_section = ""
    current_type = "single"

    # First, walk line by line to build a map of (char_offset -> state) so we
    # know which chapter/section/type each entry belongs to.
    # We split text into lines but keep track of absolute offsets.
    results: List[Dict[str, Any]] = []

    # Build a list of (offset, kind, value) markers by scanning the full text
    markers = []  # (offset, 'chapter'|'section'|'type', value)
    for m in RE_CHAPTER.finditer(full_text):
        markers.append((m.start(), "chapter", _norm(m.group(1))))
    for m in RE_SECTION.finditer(full_text):
        markers.append((m.start(), "section", _norm(m.group(1))))
    for m in RE_TYPE.finditer(full_text):
        markers.append((m.start(), "type", TYPE_MAP.get(m.group(1), "single")))

    # Sort markers by offset
    markers.sort(key=lambda x: x[0])

    # Find all entries and their answer lines
    entries = list(RE_ENTRY.finditer(full_text))
    answers = list(RE_ANSWER.finditer(full_text))

    # For each entry, find the state at its offset, then find the next answer
    # after the entry start (but before the next entry start).
    marker_idx = 0
    answer_idx = 0

    for ei, em in enumerate(entries):
        entry_offset = em.start()
        entry_num = em.group(1)
        entry_end = entries[ei + 1].start() if ei + 1 < len(entries) else len(full_text)

        # Advance marker state up to entry_offset
        while marker_idx < len(markers) and markers[marker_idx][0] <= entry_offset:
            _, kind, val = markers[marker_idx]
            if kind == "chapter":
                current_chapter = val
            elif kind == "section":
                current_section = val
            elif kind == "type":
                current_type = val
            marker_idx += 1

        # Find the first answer in (entry_offset, entry_end)
        while answer_idx < len(answers) and answers[answer_idx].start() < entry_offset:
            answer_idx += 1
        if answer_idx >= len(answers) or answers[answer_idx].start() >= entry_end:
            # No answer for this entry - skip
            continue
        am = answers[answer_idx]
        raw_answer = am.group(1).upper()
        answer_end = am.end()

        # Extract explanation text between entry start and answer line
        explanation_text = full_text[em.end():am.start()].strip()
        # Clean up: remove leading 【N】 or 【N～M】 markers and stray colons
        explanation_text = re.sub(r'^[：:\s]*', '', explanation_text)
        explanation_text = explanation_text.strip()

        # Check for group marker 【N～M】
        group_m = RE_GROUP.search(full_text, em.start(), answer_end + 50)
        if group_m:
            start_n = int(group_m.group(1))
            end_m = int(group_m.group(2))
            count = end_m - start_n + 1
            # Split answer string char by char
            if len(raw_answer) >= count:
                for i in range(count):
                    qnum = str(start_n + i)
                    results.append({
                        "question_number": qnum,
                        "chapter": current_chapter,
                        "section": current_section,
                        "question_type": current_type,
                        "answer": raw_answer[i],
                        "explanation": explanation_text,
                    })
            else:
                # Fallback: assign whole answer to each
                for i in range(count):
                    qnum = str(start_n + i)
                    results.append({
                        "question_number": qnum,
                        "chapter": current_chapter,
                        "section": current_section,
                        "question_type": current_type,
                        "answer": raw_answer,
                        "explanation": explanation_text,
                    })
        else:
            results.append({
                "question_number": entry_num,
                "chapter": current_chapter,
                "section": current_section,
                "question_type": current_type,
                "answer": raw_answer,
                "explanation": explanation_text,
            })

    return results


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else r"D:\lian\temp\1200题中药学综合 答案与解析.pdf"
    items = parse_answer_pdf(path)
    print(f"Total answers parsed: {len(items)}")
    # Stats by type
    from collections import Counter
    type_counts = Counter(i["question_type"] for i in items)
    print("By type:", dict(type_counts))
    # Show first 5 and last 5
    print("\n--- First 5 ---")
    for it in items[:5]:
        print(f"  [{it['question_type']}] {it['chapter']} > {it['section']} > Q{it['question_number']} = {it['answer']}  | {it['explanation'][:40]}...")
    print("\n--- Last 5 ---")
    for it in items[-5:]:
        print(f"  [{it['question_type']}] {it['chapter']} > {it['section']} > Q{it['question_number']} = {it['answer']}  | {it['explanation'][:40]}...")
    # Show a matching group example
    print("\n--- Matching group examples ---")
    shown = 0
    for it in items:
        if it["question_type"] == "matching" and shown < 6:
            print(f"  {it['chapter']} > {it['section']} > Q{it['question_number']} = {it['answer']}  | {it['explanation'][:50]}...")
            shown += 1
