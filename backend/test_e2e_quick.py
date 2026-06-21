# -*- coding: utf-8 -*-
"""快速E2E测试 - 只测试关键场景，使用代表性试卷"""
import requests, json, sys, random
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/exam"

passed = 0
failed = 0
errors = []

def log_pass(msg):
    global passed; passed += 1; print(f"  ✅ {msg}")

def log_fail(msg):
    global failed; failed += 1; errors.append(msg); print(f"  ❌ {msg}")

def log_info(msg):
    print(f"  ℹ️  {msg}")

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# Test 1: Health
section("Test 1: 健康检查")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    if r.status_code == 200: log_pass("服务器健康检查通过")
    else: log_fail(f"健康检查失败: {r.status_code}")
except Exception as e:
    log_fail(f"无法连接服务器: {e}"); sys.exit(1)

# Test 2: Paper list
section("Test 2: 获取试卷列表")
r = requests.get(f"{API}/papers", timeout=10)
papers = r.json()
log_pass(f"获取试卷列表成功: {len(papers)}套试卷")
papers_2025 = [p for p in papers if p["year"] == 2025]
log_info(f"2025年试卷: {len(papers_2025)}套")
for p in papers_2025:
    log_info(f"  - Paper {p['id']}: {p['subject']} ({p['question_count']}题)")

# 选代表性试卷: 2025各科 + 2023中药一(120题, 含看图题)
test_papers = [p["id"] for p in papers_2025] + [5]  # Paper 5 = 2023中药一

# Test 3: Exam mode (no answer leak)
section("Test 3: 试卷详情（考试模式 - 不含答案）")
for pid in test_papers:
    r = requests.get(f"{API}/papers/{pid}", timeout=15)
    data = r.json()
    qs = data.get("questions", [])
    has_answer = any(q.get("answer") for q in qs)
    missing_opts = [q for q in qs if not q.get("options") or not isinstance(q["options"], dict) or len(q["options"]) < 2]
    if has_answer: log_fail(f"Paper {pid}: 考试模式泄露答案!")
    if missing_opts: log_fail(f"Paper {pid}: {len(missing_opts)}题缺少选项 (ids: {[q['id'] for q in missing_opts[:3]]})")
    if not has_answer and not missing_opts: log_pass(f"Paper {pid}: {len(qs)}题, 考试模式数据完整")

# Test 4: Review mode
section("Test 4: 试卷复习模式（含答案和解析）")
for pid in test_papers:
    r = requests.get(f"{API}/papers/{pid}/review", timeout=15)
    data = r.json()
    qs = data.get("questions", [])
    no_ans = [q for q in qs if not q.get("answer")]
    no_expl = [q for q in qs if not q.get("explanation")]
    bad_opts = [q for q in qs if not isinstance(q.get("options"), dict)]
    if no_ans: log_fail(f"Paper {pid}: {len(no_ans)}题缺少答案")
    if no_expl: log_fail(f"Paper {pid}: {len(no_expl)}题缺少解析")
    if bad_opts: log_fail(f"Paper {pid}: {len(bad_opts)}题options类型错误")
    if not no_ans and not no_expl and not bad_opts: log_pass(f"Paper {pid} review: {len(qs)}题完整")

# Test 5: All correct
section("Test 5: 模拟答题 - 全部正确")
for pid in test_papers:
    r = requests.get(f"{API}/papers/{pid}/review", timeout=15)
    qs = r.json()["questions"]
    answers = [{"question_id": q["id"], "user_answer": q["answer"]} for q in qs]
    r = requests.post(f"{API}/attempts", json={"paper_id": pid, "answers": answers, "time_used_seconds": 300}, timeout=15)
    result = r.json()
    if result["correct_count"] == len(qs) and result["wrong_count"] == 0:
        log_pass(f"Paper {pid}: 全部正确 - {result['correct_count']}/{len(qs)}, 得分{result['score']}")
    else:
        log_fail(f"Paper {pid}: 正确{result['correct_count']}/{len(qs)}, 错误{result['wrong_count']}")

# Test 6: All wrong
section("Test 6: 模拟答题 - 全部错误")
for pid in test_papers:
    r = requests.get(f"{API}/papers/{pid}/review", timeout=15)
    qs = r.json()["questions"]
    answers = []
    for q in qs:
        wrong = [k for k in q["options"].keys() if k not in q["answer"]]
        answers.append({"question_id": q["id"], "user_answer": wrong[0] if wrong else "Z"})
    r = requests.post(f"{API}/attempts", json={"paper_id": pid, "answers": answers, "time_used_seconds": 600}, timeout=15)
    result = r.json()
    if result["correct_count"] == 0: log_pass(f"Paper {pid}: 全部错误 - 0/{len(qs)}, 得分{result['score']}")
    else: log_fail(f"Paper {pid}: 全部错误测试失败 - 正确{result['correct_count']}")

# Test 7: Unanswered
section("Test 7: 模拟答题 - 全部未答")
for pid in test_papers:
    r = requests.get(f"{API}/papers/{pid}/review", timeout=15)
    qs = r.json()["questions"]
    answers = [{"question_id": q["id"], "user_answer": ""} for q in qs]
    r = requests.post(f"{API}/attempts", json={"paper_id": pid, "answers": answers, "time_used_seconds": 100}, timeout=15)
    result = r.json()
    if result["unanswered"] == len(qs): log_pass(f"Paper {pid}: 全部未答 - {result['unanswered']}题未答")
    else: log_fail(f"Paper {pid}: 未答测试失败 - 未答{result['unanswered']}/{len(qs)}")

# Test 8: X-type shuffled
section("Test 8: X型题乱序答案匹配")
for pid in test_papers:
    r = requests.get(f"{API}/papers/{pid}/review", timeout=15)
    qs = r.json()["questions"]
    x_qs = [q for q in qs if q["question_type"] == "X"]
    if not x_qs: continue
    answers = []
    for q in qs:
        if q["question_type"] == "X":
            shuffled = ''.join(random.sample(q["answer"], len(q["answer"])))
            answers.append({"question_id": q["id"], "user_answer": shuffled})
        else:
            answers.append({"question_id": q["id"], "user_answer": q["answer"]})
    r = requests.post(f"{API}/attempts", json={"paper_id": pid, "answers": answers, "time_used_seconds": 300}, timeout=15)
    result = r.json()
    if result["correct_count"] == len(qs): log_pass(f"Paper {pid}: X型题乱序匹配正确 ({len(x_qs)}道X型题)")
    else: log_fail(f"Paper {pid}: X型题乱序匹配失败 - 正确{result['correct_count']}/{len(qs)}")

# Test 9: B-type shared stem
section("Test 9: B型题共享题干")
for pid in test_papers:
    r = requests.get(f"{API}/papers/{pid}", timeout=15)
    qs = r.json()["questions"]
    b_qs = [q for q in qs if q["question_type"] == "B"]
    if not b_qs: continue
    no_shared = [q for q in b_qs if not q.get("shared_stem")]
    if no_shared: log_fail(f"Paper {pid}: {len(no_shared)}道B型题缺少shared_stem")
    else: log_pass(f"Paper {pid}: {len(b_qs)}道B型题均有shared_stem")

# Test 10: Draft save/restore/delete
section("Test 10: 草稿保存/恢复/删除")
test_pid = papers_2025[0]["id"]
r = requests.get(f"{API}/papers/{test_pid}", timeout=10)
qs = r.json()["questions"]
requests.delete(f"{API}/drafts/{test_pid}", timeout=5)
partial = [{"question_id": q["id"], "user_answer": list(q["options"].keys())[0]} for q in qs[:len(qs)//2]]
partial += [{"question_id": q["id"], "user_answer": ""} for q in qs[len(qs)//2:]]
r = requests.post(f"{API}/drafts", json={"paper_id": test_pid, "answers": partial, "time_used_seconds": 120, "current_index": 5}, timeout=10)
if r.status_code == 200: log_pass("草稿保存成功")
else: log_fail(f"草稿保存失败: {r.status_code}")
r = requests.get(f"{API}/drafts/{test_pid}", timeout=10)
if r.status_code == 200 and r.json() and r.json().get("answers"):
    restored = len([a for a in r.json()["answers"] if a["user_answer"]])
    expected = len(qs) // 2
    if restored == expected: log_pass(f"草稿恢复成功: {restored}题已答")
    else: log_fail(f"草稿恢复数量不匹配: 期望{expected}, 实际{restored}")
else: log_fail("草稿恢复失败")
r = requests.delete(f"{API}/drafts/{test_pid}", timeout=10)
if r.status_code == 200: log_pass("草稿删除成功")
else: log_fail(f"草稿删除失败: {r.status_code}")

# Test 11: Attempt history
section("Test 11: 考试记录列表")
r = requests.get(f"{API}/attempts?limit=100", timeout=10)
if r.status_code == 200:
    attempts = r.json()
    log_pass(f"获取考试记录成功: {len(attempts)}条")
else: log_fail(f"获取考试记录失败: {r.status_code}")

# Test 12: Attempt detail
section("Test 12: 考试记录详情")
r = requests.get(f"{API}/attempts?limit=1", timeout=10)
if r.status_code == 200 and r.json():
    aid = r.json()[0]["id"]
    r = requests.get(f"{API}/attempts/{aid}", timeout=10)
    if r.status_code == 200:
        d = r.json()
        required = ["attempt_id", "paper_id", "total_questions", "correct_count", "wrong_count", "unanswered", "score", "answers"]
        missing = [f for f in required if f not in d]
        if not missing: log_pass(f"考试记录详情获取成功: {len(d['answers'])}题答题详情")
        else: log_fail(f"考试记录详情缺少字段: {missing}")
    else: log_fail(f"获取考试记录详情失败: {r.status_code}")
else: log_fail("无考试记录可测试")

# Test 13: Edge cases
section("Test 13: 边界情况")
r = requests.get(f"{API}/papers/99999", timeout=5)
if r.status_code == 404: log_pass("不存在的试卷返回404")
else: log_fail(f"不存在的试卷应返回404, 实际{r.status_code}")
r = requests.get(f"{API}/attempts/99999", timeout=5)
if r.status_code == 404: log_pass("不存在的考试记录返回404")
else: log_fail(f"不存在的考试记录应返回404, 实际{r.status_code}")
r = requests.post(f"{API}/attempts", json={"paper_id": 99999, "answers": [], "time_used_seconds": 0}, timeout=5)
if r.status_code == 404: log_pass("提交不存在的试卷返回404")
else: log_fail(f"提交不存在的试卷应返回404, 实际{r.status_code}")

# Test 14: 2025 deep validation
section("Test 14: 2025年试卷深度验证")
for pid in [p["id"] for p in papers_2025]:
    r = requests.get(f"{API}/papers/{pid}/review", timeout=15)
    data = r.json()
    qs = data["questions"]
    types = {}
    for q in qs:
        t = q["question_type"]; types[t] = types.get(t, 0) + 1
    log_info(f"Paper {pid} ({data['subject']}): {len(qs)}题 - {types}")
    issues = []
    for q in qs:
        if not q["stem"] or len(q["stem"]) < 5: issues.append(f"Q{q['question_number']}: 题干为空")
        opts = q["options"]
        if not isinstance(opts, dict) or len(opts) < 2: issues.append(f"Q{q['question_number']}: 选项无效")
        if not q["answer"]: issues.append(f"Q{q['question_number']}: 答案为空")
        if not q["explanation"]: issues.append(f"Q{q['question_number']}: 解析为空")
    if issues:
        for i in issues[:5]: log_fail(f"  Paper {pid}: {i}")
    else: log_pass(f"Paper {pid}: 所有题目验证通过")

# Test 15: Answer matching accuracy
section("Test 15: 答案匹配准确性")
for pid in [p["id"] for p in papers_2025]:
    r = requests.get(f"{API}/papers/{pid}/review", timeout=15)
    qs = r.json()["questions"]
    answers = [{"question_id": q["id"], "user_answer": q["answer"]} for q in qs]
    r = requests.post(f"{API}/attempts", json={"paper_id": pid, "answers": answers, "time_used_seconds": 300}, timeout=15)
    result = r.json()
    wrong = sum(1 for a in result["answers"] if not a["is_correct"])
    if wrong == 0: log_pass(f"Paper {pid}: 所有正确答案均被正确判分")
    else: log_fail(f"Paper {pid}: {wrong}题被判错")

# Summary
section("测试总结")
total = passed + failed
print(f"\n  总测试数: {total}")
print(f"  ✅ 通过: {passed}")
print(f"  ❌ 失败: {failed}")
if errors:
    print(f"\n  失败列表:")
    for e in errors: print(f"    - {e}")
