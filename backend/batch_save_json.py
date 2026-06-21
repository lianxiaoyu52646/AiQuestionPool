# -*- coding: utf-8 -*-
"""通用批量保存题目 - 从JSON文件读取并保存到数据库
用法: python batch_save_json.py <paper_id> <json_file>
JSON文件格式: [{"question_number":1,...}, ...]
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from save_exam_question import save_question

if len(sys.argv) < 3:
    print("用法: python batch_save_json.py <paper_id> <json_file>")
    sys.exit(1)

paper_id = int(sys.argv[1])
json_file = sys.argv[2]

with open(json_file, 'r', encoding='utf-8') as f:
    questions = json.load(f)

for q in questions:
    save_question(paper_id, q)

print(f"\n共保存{len(questions)}题到试卷{paper_id}")
