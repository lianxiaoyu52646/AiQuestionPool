"""E2E test 2: mixed correct/wrong answers, and all wrong answers"""
import json, urllib.request

base = "http://localhost:8000/api/exam"

# 获取试卷和题目（含答案）
papers = json.loads(urllib.request.urlopen(f"{base}/papers").read())
paper = papers[0]
review = json.loads(urllib.request.urlopen(f"{base}/papers/{paper['id']}/review").read())
questions = review['questions']

def submit_attempt(answers, time_used=3600):
    payload = {
        "paper_id": paper['id'],
        "answers": answers,
        "time_used_seconds": time_used
    }
    req = urllib.request.Request(
        f"{base}/attempts",
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    return json.loads(urllib.request.urlopen(req).read())

# ========== 测试1: 全部错误答案 ==========
print("=" * 50)
print("测试1: 全部错误答案")
print("=" * 50)

wrong_answers = []
for q in questions:
    correct = q['answer'].strip()
    # 生成一个错误答案
    if len(correct) == 1:
        # 单选题，选一个不同的选项
        options = ['A', 'B', 'C', 'D', 'E']
        wrong = next((o for o in options if o != correct), 'A')
    else:
        # 多选题，改成只选第一个选项
        wrong = 'A' if 'A' not in correct else 'B'
    wrong_answers.append({"question_id": q['id'], "user_answer": wrong})

result1 = submit_attempt(wrong_answers)
print(f"总分: {result1['score']}")
print(f"答对: {result1['correct_count']}, 答错: {result1['wrong_count']}, 未答: {result1['unanswered']}")
print(f"是否通过: {result1['passed']}")
assert result1['score'] == 0, f"分数应为0，实际{result1['score']}"
assert result1['correct_count'] == 0, f"答对应为0，实际{result1['correct_count']}"
assert result1['wrong_count'] == 120, f"答错应为120，实际{result1['wrong_count']}"
assert result1['unanswered'] == 0
assert result1['passed'] == False
# 验证所有is_correct=False
for ans in result1['answers']:
    assert ans['is_correct'] == False, f"题{ans['question_number']}应为错误，实际{ans['is_correct']}"
print("✅ 全部错误答案测试通过！")

# ========== 测试2: 部分正确（前60题正确，后60题错误）==========
print("\n" + "=" * 50)
print("测试2: 前60题正确，后60题错误")
print("=" * 50)

mixed_answers = []
for i, q in enumerate(questions):
    if i < 60:
        ans = q['answer'].strip()
    else:
        correct = q['answer'].strip()
        if len(correct) == 1:
            options = ['A', 'B', 'C', 'D', 'E']
            ans = next((o for o in options if o != correct), 'A')
        else:
            ans = 'A' if 'A' not in correct else 'B'
    mixed_answers.append({"question_id": q['id'], "user_answer": ans})

result2 = submit_attempt(mixed_answers)
print(f"总分: {result2['score']}")
print(f"答对: {result2['correct_count']}, 答错: {result2['wrong_count']}, 未答: {result2['unanswered']}")
print(f"是否通过: {result2['passed']}")
assert result2['score'] == 60, f"分数应为60，实际{result2['score']}"
assert result2['correct_count'] == 60, f"答对应为60，实际{result2['correct_count']}"
assert result2['wrong_count'] == 60, f"答错应为60，实际{result2['wrong_count']}"
assert result2['unanswered'] == 0
assert result2['passed'] == False  # 60 < 72
print("✅ 部分正确答案测试通过！")

# ========== 测试3: 部分未答（前40题正确，中间40题未答，后40题错误）==========
print("\n" + "=" * 50)
print("测试3: 前40题正确，中间40题未答，后40题错误")
print("=" * 50)

partial_answers = []
for i, q in enumerate(questions):
    if i < 40:
        ans = q['answer'].strip()
        partial_answers.append({"question_id": q['id'], "user_answer": ans})
    elif i < 80:
        # 不提交这40题（未答）
        pass
    else:
        correct = q['answer'].strip()
        if len(correct) == 1:
            options = ['A', 'B', 'C', 'D', 'E']
            ans = next((o for o in options if o != correct), 'A')
        else:
            ans = 'A' if 'A' not in correct else 'B'
        partial_answers.append({"question_id": q['id'], "user_answer": ans})

result3 = submit_attempt(partial_answers)
print(f"总分: {result3['score']}")
print(f"答对: {result3['correct_count']}, 答错: {result3['wrong_count']}, 未答: {result3['unanswered']}")
print(f"是否通过: {result3['passed']}")
assert result3['score'] == 40, f"分数应为40，实际{result3['score']}"
assert result3['correct_count'] == 40, f"答对应为40，实际{result3['correct_count']}"
assert result3['wrong_count'] == 40, f"答错应为40，实际{result3['wrong_count']}"
assert result3['unanswered'] == 40, f"未答应为40，实际{result3['unanswered']}"
assert result3['passed'] == False  # 40 < 72

# 验证未答题的is_correct=None
none_count = sum(1 for a in result3['answers'] if a['is_correct'] is None)
true_count = sum(1 for a in result3['answers'] if a['is_correct'] == True)
false_count = sum(1 for a in result3['answers'] if a['is_correct'] == False)
print(f"is_correct统计: True={true_count}, False={false_count}, None={none_count}")
assert none_count == 40, f"None应为40，实际{none_count}"
assert true_count == 40
assert false_count == 40
print("✅ 部分未答测试通过！")

# ========== 测试4: 刚好及格（72题正确）==========
print("\n" + "=" * 50)
print("测试4: 前72题正确，后48题错误（刚好及格）")
print("=" * 50)

pass_answers = []
for i, q in enumerate(questions):
    if i < 72:
        ans = q['answer'].strip()
    else:
        correct = q['answer'].strip()
        if len(correct) == 1:
            options = ['A', 'B', 'C', 'D', 'E']
            ans = next((o for o in options if o != correct), 'A')
        else:
            ans = 'A' if 'A' not in correct else 'B'
    pass_answers.append({"question_id": q['id'], "user_answer": ans})

result4 = submit_attempt(pass_answers)
print(f"总分: {result4['score']}")
print(f"答对: {result4['correct_count']}, 答错: {result4['wrong_count']}, 未答: {result4['unanswered']}")
print(f"是否通过: {result4['passed']}")
assert result4['score'] == 72, f"分数应为72，实际{result4['score']}"
assert result4['correct_count'] == 72
assert result4['wrong_count'] == 48
assert result4['passed'] == True  # 72 >= 72 刚好及格
print("✅ 刚好及格测试通过！")

# ========== 测试5: X型题（多选题）顺序无关性 ==========
print("\n" + "=" * 50)
print("测试5: X型题答案顺序无关性验证")
print("=" * 50)

x_questions = [q for q in questions if q['question_type'] == 'X']
print(f"X型题数量: {len(x_questions)}")

# 将X型题答案打乱顺序提交
x_answers = []
for q in questions:
    if q['question_type'] == 'X':
        correct = q['answer'].strip()
        # 打乱顺序
        reversed_ans = correct[::-1]
        x_answers.append({"question_id": q['id'], "user_answer": reversed_ans})
    else:
        x_answers.append({"question_id": q['id'], "user_answer": q['answer'].strip()})

result5 = submit_attempt(x_answers)
print(f"总分: {result5['score']}")
print(f"答对: {result5['correct_count']}, 答错: {result5['wrong_count']}")
assert result5['score'] == 120, f"X型题顺序打乱后应仍为120，实际{result5['score']}"
print("✅ X型题顺序无关性验证通过！")

# ========== 测试6: 空答案提交 ==========
print("\n" + "=" * 50)
print("测试6: 空答案提交（全部未答）")
print("=" * 50)

result6 = submit_attempt([], time_used=60)
print(f"总分: {result6['score']}")
print(f"答对: {result6['correct_count']}, 答错: {result6['wrong_count']}, 未答: {result6['unanswered']}")
assert result6['score'] == 0
assert result6['correct_count'] == 0
assert result6['wrong_count'] == 0
assert result6['unanswered'] == 120
assert result6['passed'] == False
print("✅ 空答案提交测试通过！")

print("\n" + "=" * 50)
print("🎉 所有E2E测试场景完成！")
print("=" * 50)
print("""
测试总结:
1. ✅ 全部正确(120/120) → 满分120，通过
2. ✅ 全部错误(0/120) → 0分，不通过
3. ✅ 部分 correct(60/120) → 60分，不通过
4. ✅ 部分未答(40正确/40未答/40错误) → 40分，不通过，is_correct三态正确
5. ✅ 刚好及格(72/120) → 72分，通过
6. ✅ X型题顺序无关性 → 打乱顺序仍判对
7. ✅ 空答案提交 → 0分，全部未答
""")
