# -*- coding: utf-8 -*-
"""Analyze answer PDF structure for regex parser design"""
import fitz
import re

doc = fitz.open(r'D:\lian\temp\1200题中药学综合 答案与解析.pdf')

# 1. Collect all section/type headers and their page numbers
print("=== Chapter/Section/Type markers ===")
for i in range(len(doc)):
    t = doc[i].get_text()
    for line in t.split('\n'):
        ls = line.strip()
        if re.match(r'^第[一二三四五六七八九十]+章', ls) and '部分' not in ls and '//' not in ls and len(ls) < 40:
            print(f'p{i+1} CHAPTER: {ls}')
        elif re.match(r'^第[一二三四五六七八九十]+节', ls) and len(ls) < 40:
            print(f'p{i+1} SECTION: {ls}')
        elif ls in ['单项选择题', '多项选择题', '配伍选择题', '综合分析题']:
            print(f'p{i+1} TYPE: {ls}')
        elif '部分' in ls and ls.startswith('第'):
            print(f'p{i+1} PART: {ls}')

# 2. Sample answer entry patterns - find all "答案：" occurrences
print("\n=== Answer patterns sample ===")
answer_count = 0
group_patterns = []
for i in range(len(doc)):
    t = doc[i].get_text()
    for m in re.finditer(r'答案[：:]\s*([A-Za-z]+)', t):
        ans = m.group(1)
        answer_count += 1
        if answer_count <= 30:
            # context around
            start = max(0, m.start() - 80)
            ctx = t[start:m.end()].replace('\n', ' ')
            print(f'p{i+1} [{answer_count}] ...{ctx[-80:]} => {ans}')
print(f'\nTotal 答案: occurrences: {answer_count}')

# 3. Check group patterns like 【21～22】
print("\n=== Group patterns (配伍) ===")
group_count = 0
for i in range(len(doc)):
    t = doc[i].get_text()
    for m in re.finditer(r'【(\d+)[～~-](\d+)】', t):
        group_count += 1
        if group_count <= 20:
            start = max(0, m.start() - 20)
            end = min(len(t), m.end() + 100)
            ctx = t[start:end].replace('\n', ' ')
            print(f'p{i+1} [{group_count}] ...{ctx}...')
print(f'\nTotal group markers: {group_count}')

# 4. Check question number patterns: "1.解析" or "1.解析："
print("\n=== Question entry patterns ===")
entry_count = 0
for i in range(len(doc)):
    t = doc[i].get_text()
    for m in re.finditer(r'(\d+)[.．、]\s*解析', t):
        entry_count += 1
        if entry_count <= 20:
            start = max(0, m.start() - 10)
            end = min(len(t), m.end() + 30)
            ctx = t[start:end].replace('\n', ' ')
            print(f'p{i+1} [{entry_count}] ...{ctx}...')
print(f'\nTotal question entries: {entry_count}')

doc.close()
