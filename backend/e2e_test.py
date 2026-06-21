"""E2E test: submit all correct answers and verify score"""
import json, urllib.request

base = "http://localhost:8000/api/exam"

# 1. 获取试卷列表
papers = json.loads(urllib.request.urlopen(f"{base}/papers").read())
print(f"试卷数量: {len(papers)}")
paper = papers[0]
print(f"试卷: {paper['title']}, 及格线: {paper['pass_score']}, 题目数: {paper['total_questions']}")

# 2. 获取包含答案的题目（review模式）
review = json.loads(urllib.request.urlopen(f"{base}/papers/{paper['id']}/review").read())
questions = review['questions']
print(f"获取到题目数: {len(questions)}")

# 3. 构建全部正确答案
answers = []
type_count = {}
for q in questions:
    ans = q['answer'].strip()
    answers.append({"question_id": q['id'], "user_answer": ans})
    qt = q['question_type']
    type_count[qt] = type_count.get(qt, 0) + 1

print(f"题型分布: {type_count}")
print(f"前5题答案: {[(q['question_number'], q['answer']) for q in questions[:5]]}")
print(f"最后5题答案: {[(q['question_number'], q['answer']) for q in questions[-5:]]}")

# 4. 提交答卷（全部正确）
payload = {
    "paper_id": paper['id'],
    "answers": answers,
    "time_used_seconds": 3600
}
req = urllib.request.Request(
    f"{base}/attempts",
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
result = json.loads(urllib.request.urlopen(req).read())

print(f"\n=== 提交结果（全部正确）===")
print(f"总分: {result['score']}")
print(f"总题数: {result['total_questions']}")
print(f"答对: {result['correct_count']}")
print(f"答错: {result['wrong_count']}")
print(f"未答: {result['unanswered']}")
print(f"及格线: {result['pass_score']}")
print(f"是否通过: {result['passed']}")
print(f"用时: {result['time_used_seconds']}秒")

# 验证
assert result['score'] == 120, f"分数应为120，实际{result['score']}"
assert result['correct_count'] == 120, f"答对应为120，实际{result['correct_count']}"
assert result['wrong_count'] == 0, f"答错应为0，实际{result['wrong_count']}"
assert result['unanswered'] == 0, f"未答应为0，实际{result['unanswered']}"
assert result['passed'] == True, f"应通过，实际{result['passed']}"
print("\n✅ 全部正确提交验证通过！")

# 5. 验证每道题的is_correct
for ans in result['answers']:
    assert ans['is_correct'] == True, f"题{ans['question_number']}应为正确，实际{ans['is_correct']}"
print(f"✅ 所有{len(result['answers'])}题is_correct=True 验证通过！")

# 6. 验证attempt列表
attempts = json.loads(urllib.request.urlopen(f"{base}/attempts").read())
latest = attempts[0]  # 按finished_at desc排序，第一个是最新
print(f"\n=== Attempt列表最新记录 ===")
print(f"id: {latest['id']}")
print(f"score: {latest['score']}")
print(f"pass_score: {latest['pass_score']}")
print(f"correct: {latest['correct_count']}, wrong: {latest['wrong_count']}, unanswered: {latest['unanswered']}")
assert latest['score'] == 120, f"列表中分数应为120，实际{latest['score']}"
assert latest['pass_score'] == 72, f"及格线应为72，实际{latest['pass_score']}"
print("✅ Attempt列表验证通过！")

# 7. 验证attempt详情
detail = json.loads(urllib.request.urlopen(f"{base}/attempts/{result['attempt_id']}").read())
print(f"\n=== Attempt详情 ===")
print(f"score: {detail['score']}")
print(f"correct: {detail['correct_count']}, wrong: {detail['wrong_count']}, unanswered: {detail['unanswered']}")
print(f"answers count: {len(detail['answers'])}")
assert detail['score'] == 120
assert len(detail['answers']) == 120
# 检查所有答案详情
correct_in_detail = sum(1 for a in detail['answers'] if a['is_correct'] == True)
print(f"详情中is_correct=True的数量: {correct_in_detail}")
assert correct_in_detail == 120
print("✅ Attempt详情验证通过！")

print("\n" + "="*50)
print("🎉 全部正确答案 E2E 测试完成！")
print("="*50)
