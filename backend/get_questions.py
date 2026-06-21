"""获取题目信息，用于浏览器E2E测试参考"""
import json, urllib.request

base = "http://localhost:8000/api/exam"
review = json.loads(urllib.request.urlopen(f"{base}/papers/1/review").read())
questions = review['questions']

# 打印前20题的题号、题型、正确答案、选项
for q in questions[:20]:
    opts = list(q['options'].keys())
    print(f"题{q['question_number']:3d} [{q['question_type']}] 正确:{q['answer']:6s} 选项:{opts} - {q['stem'][:40]}")
