# -*- coding: utf-8 -*-
"""
E2E 考试系统测试脚本
测试所有试卷（重点测试2025年新增试卷）的完整答题流程：
1. 获取试卷列表
2. 获取试卷详情（考试模式）
3. 获取试卷复习模式
4. 模拟答题（全部正确、全部错误、部分正确、未作答）
5. 提交答卷并验证判分
6. 查看考试记录
7. 草稿保存/恢复/删除
8. 边界情况测试
"""
import requests
import json
import sys
import time
import random

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/exam"

passed = 0
failed = 0
errors = []


def log_pass(msg):
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def log_fail(msg):
    global failed
    failed += 1
    errors.append(msg)
    print(f"  ❌ {msg}")


def log_info(msg):
    print(f"  ℹ️  {msg}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ========== Test 1: Health Check ==========
section("Test 1: 健康检查")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    if r.status_code == 200:
        log_pass("服务器健康检查通过")
    else:
        log_fail(f"健康检查失败: {r.status_code}")
except Exception as e:
    log_fail(f"无法连接服务器: {e}")
    sys.exit(1)


# ========== Test 2: Get Papers List ==========
section("Test 2: 获取试卷列表")
try:
    r = requests.get(f"{API}/papers", timeout=10)
    if r.status_code != 200:
        log_fail(f"获取试卷列表失败: {r.status_code}")
        sys.exit(1)
    
    papers = r.json()
    log_pass(f"获取试卷列表成功: {len(papers)}套试卷")
    
    # Verify all papers have required fields
    required_fields = ["id", "subject", "year", "title", "total_questions", "time_limit_minutes", "pass_score", "question_count"]
    for p in papers:
        for field in required_fields:
            if field not in p:
                log_fail(f"试卷 {p.get('id', '?')} 缺少字段: {field}")
                break
    
    # Check 2025 papers exist
    papers_2025 = [p for p in papers if p["year"] == 2025]
    if len(papers_2025) >= 3:
        log_pass(f"2025年试卷存在: {len(papers_2025)}套")
        for p in papers_2025:
            log_info(f"  - Paper {p['id']}: {p['subject']} ({p['question_count']}题)")
    else:
        log_fail(f"2025年试卷不足: 期望>=3, 实际={len(papers_2025)}")
    
    # Check all papers have questions
    empty_papers = [p for p in papers if p["question_count"] == 0]
    if not empty_papers:
        log_pass("所有试卷都有题目")
    else:
        log_fail(f"有空试卷: {[p['id'] for p in empty_papers]}")
    
    # Verify question counts
    for p in papers:
        if p["question_count"] > 0:
            log_info(f"  Paper {p['id']}: {p['year']} {p['subject']} - {p['question_count']}题")
    
except Exception as e:
    log_fail(f"获取试卷列表异常: {e}")
    sys.exit(1)


# ========== Test 3: Paper Detail (Exam Mode) ==========
section("Test 3: 试卷详情（考试模式 - 不含答案）")
all_paper_ids = [p["id"] for p in papers]

for paper_id in all_paper_ids:
    try:
        r = requests.get(f"{API}/papers/{paper_id}", timeout=15)
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: 获取详情失败: {r.status_code}")
            continue
        
        data = r.json()
        questions = data.get("questions", [])
        
        if not questions:
            log_fail(f"Paper {paper_id}: 没有题目")
            continue
        
        # Verify questions don't contain answers in exam mode
        has_answer = any(q.get("answer") for q in questions)
        has_explanation = any(q.get("explanation") for q in questions)
        
        if has_answer:
            log_fail(f"Paper {paper_id}: 考试模式返回了答案！")
        if has_explanation:
            log_fail(f"Paper {paper_id}: 考试模式返回了解析！")
        
        # Verify all questions have required fields
        missing_stem = [q for q in questions if not q.get("stem") or len(q["stem"]) < 5]
        missing_options = [q for q in questions if not q.get("options") or not isinstance(q["options"], dict) or len(q["options"]) < 2]
        missing_type = [q for q in questions if not q.get("question_type")]
        
        if missing_stem:
            log_fail(f"Paper {paper_id}: {len(missing_stem)}题缺少题干")
        if missing_options:
            log_fail(f"Paper {paper_id}: {len(missing_options)}题缺少选项 (ids: {[q['id'] for q in missing_options[:3]]})")
        if missing_type:
            log_fail(f"Paper {paper_id}: {len(missing_type)}题缺少题型")
        
        if not has_answer and not has_explanation and not missing_stem and not missing_options and not missing_type:
            log_pass(f"Paper {paper_id}: {len(questions)}题, 考试模式数据完整（无答案泄露）")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: 获取详情异常: {e}")


# ========== Test 4: Paper Review Mode ==========
section("Test 4: 试卷复习模式（含答案和解析）")
for paper_id in all_paper_ids:
    try:
        r = requests.get(f"{API}/papers/{paper_id}/review", timeout=15)
        if r.status_code != 200:
            log_fail(f"Paper {paper_id} review: 失败: {r.status_code} - {r.text[:200]}")
            continue
        
        data = r.json()
        questions = data.get("questions", [])
        
        # Verify questions DO contain answers in review mode
        no_answer = [q for q in questions if not q.get("answer")]
        no_explanation = [q for q in questions if not q.get("explanation")]
        
        if no_answer:
            log_fail(f"Paper {paper_id} review: {len(no_answer)}题缺少答案")
        if no_explanation:
            log_fail(f"Paper {paper_id} review: {len(no_explanation)}题缺少解析")
        
        # Verify options are dict type
        bad_options = [q for q in questions if not isinstance(q.get("options"), dict)]
        if bad_options:
            log_fail(f"Paper {paper_id} review: {len(bad_options)}题options不是dict类型")
        
        if not no_answer and not no_explanation and not bad_options:
            log_pass(f"Paper {paper_id} review: {len(questions)}题, 答案和解析完整")
        
    except Exception as e:
        log_fail(f"Paper {paper_id} review: 异常: {e}")


# ========== Test 5: Simulate Exam - All Correct ==========
section("Test 5: 模拟答题 - 全部正确")
for paper_id in all_paper_ids:
    try:
        # Get review mode to get correct answers
        r = requests.get(f"{API}/papers/{paper_id}/review", timeout=15)
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: 无法获取复习数据")
            continue
        
        questions = r.json()["questions"]
        
        # Submit all correct answers
        answers = []
        for q in questions:
            answers.append({
                "question_id": q["id"],
                "user_answer": q["answer"]
            })
        
        r = requests.post(f"{API}/attempts", json={
            "paper_id": paper_id,
            "answers": answers,
            "time_used_seconds": 300
        }, timeout=15)
        
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: 提交答卷失败: {r.status_code} - {r.text[:200]}")
            continue
        
        result = r.json()
        
        # Verify all correct
        if result["correct_count"] != len(questions):
            log_fail(f"Paper {paper_id}: 全部正确测试失败 - 期望{len(questions)}题正确, 实际{result['correct_count']}题")
        elif result["wrong_count"] != 0:
            log_fail(f"Paper {paper_id}: 全部正确测试失败 - 错误数{result['wrong_count']}")
        elif result["unanswered"] != 0:
            log_fail(f"Paper {paper_id}: 全部正确测试失败 - 未答{result['unanswered']}")
        elif result["score"] != len(questions):
            log_fail(f"Paper {paper_id}: 全部正确测试失败 - 分数{result['score']}, 期望{len(questions)}")
        else:
            log_pass(f"Paper {paper_id}: 全部正确 - {result['correct_count']}/{len(questions)}题正确, 得分{result['score']}")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: 全部正确测试异常: {e}")


# ========== Test 6: Simulate Exam - All Wrong ==========
section("Test 6: 模拟答题 - 全部错误")
for paper_id in all_paper_ids:
    try:
        r = requests.get(f"{API}/papers/{paper_id}/review", timeout=15)
        if r.status_code != 200:
            continue
        
        questions = r.json()["questions"]
        
        # Submit all wrong answers (pick a different option)
        answers = []
        for q in questions:
            correct = q["answer"]
            options = q["options"]
            # Find a wrong answer
            wrong_opts = [k for k in options.keys() if k not in correct]
            wrong_answer = wrong_opts[0] if wrong_opts else "Z"
            answers.append({
                "question_id": q["id"],
                "user_answer": wrong_answer
            })
        
        r = requests.post(f"{API}/attempts", json={
            "paper_id": paper_id,
            "answers": answers,
            "time_used_seconds": 600
        }, timeout=15)
        
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: 全部错误提交失败: {r.status_code}")
            continue
        
        result = r.json()
        
        if result["correct_count"] == 0 and result["wrong_count"] == len(questions):
            log_pass(f"Paper {paper_id}: 全部错误 - 0/{len(questions)}题正确, 得分{result['score']}")
        else:
            log_fail(f"Paper {paper_id}: 全部错误测试失败 - 正确{result['correct_count']}, 错误{result['wrong_count']}")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: 全部错误测试异常: {e}")


# ========== Test 7: Simulate Exam - Unanswered ==========
section("Test 7: 模拟答题 - 全部未答")
for paper_id in all_paper_ids:
    try:
        r = requests.get(f"{API}/papers/{paper_id}/review", timeout=15)
        if r.status_code != 200:
            continue
        
        questions = r.json()["questions"]
        
        # Submit empty answers
        answers = [{"question_id": q["id"], "user_answer": ""} for q in questions]
        
        r = requests.post(f"{API}/attempts", json={
            "paper_id": paper_id,
            "answers": answers,
            "time_used_seconds": 100
        }, timeout=15)
        
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: 未答提交失败: {r.status_code}")
            continue
        
        result = r.json()
        
        if result["unanswered"] == len(questions) and result["correct_count"] == 0:
            log_pass(f"Paper {paper_id}: 全部未答 - {result['unanswered']}题未答, 得分{result['score']}")
        else:
            log_fail(f"Paper {paper_id}: 未答测试失败 - 未答{result['unanswered']}, 正确{result['correct_count']}")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: 未答测试异常: {e}")


# ========== Test 8: X-type Question Answer Matching ==========
section("Test 8: X型题(多选题)答案匹配测试")
for paper_id in all_paper_ids:
    try:
        r = requests.get(f"{API}/papers/{paper_id}/review", timeout=15)
        if r.status_code != 200:
            continue
        
        questions = r.json()["questions"]
        x_questions = [q for q in questions if q["question_type"] == "X"]
        
        if not x_questions:
            continue
        
        # Test: submit correct answer with different order
        answers = []
        for q in questions:
            if q["question_type"] == "X":
                # Shuffle the answer to test order independence
                shuffled = ''.join(random.sample(q["answer"], len(q["answer"])))
                answers.append({"question_id": q["id"], "user_answer": shuffled})
            else:
                answers.append({"question_id": q["id"], "user_answer": q["answer"]})
        
        r = requests.post(f"{API}/attempts", json={
            "paper_id": paper_id,
            "answers": answers,
            "time_used_seconds": 300
        }, timeout=15)
        
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: X型题测试提交失败")
            continue
        
        result = r.json()
        
        # All should be correct (order shouldn't matter)
        if result["correct_count"] == len(questions):
            log_pass(f"Paper {paper_id}: X型题乱序答案匹配正确 ({len(x_questions)}道X型题)")
        else:
            log_fail(f"Paper {paper_id}: X型题乱序匹配失败 - 正确{result['correct_count']}/{len(questions)}")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: X型题测试异常: {e}")


# ========== Test 9: B-type Question Shared Stem ==========
section("Test 9: B型题共享题干测试")
for paper_id in all_paper_ids:
    try:
        r = requests.get(f"{API}/papers/{paper_id}", timeout=15)
        if r.status_code != 200:
            continue
        
        questions = r.json()["questions"]
        b_questions = [q for q in questions if q["question_type"] == "B"]
        
        if not b_questions:
            continue
        
        # Check shared_stem is present for B-type questions
        no_shared = [q for q in b_questions if not q.get("shared_stem")]
        if no_shared:
            log_fail(f"Paper {paper_id}: {len(no_shared)}道B型题缺少shared_stem")
        else:
            log_pass(f"Paper {paper_id}: {len(b_questions)}道B型题均有shared_stem")
        
        # Check group_id
        no_group = [q for q in b_questions if not q.get("group_id")]
        if no_group:
            log_fail(f"Paper {paper_id}: {len(no_group)}道B型题缺少group_id")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: B型题测试异常: {e}")


# ========== Test 10: Draft Save/Restore/Delete ==========
section("Test 10: 草稿保存/恢复/删除")
test_paper_id = papers_2025[0]["id"] if papers_2025 else papers[0]["id"]

try:
    # Get paper detail
    r = requests.get(f"{API}/papers/{test_paper_id}", timeout=10)
    questions = r.json()["questions"]
    
    # Delete any existing draft first
    requests.delete(f"{API}/drafts/{test_paper_id}", timeout=5)
    
    # Save draft with partial answers
    partial_answers = []
    for i, q in enumerate(questions):
        if i < len(questions) // 2:
            partial_answers.append({
                "question_id": q["id"],
                "user_answer": list(q["options"].keys())[0]  # Pick first option
            })
        else:
            partial_answers.append({
                "question_id": q["id"],
                "user_answer": ""
            })
    
    r = requests.post(f"{API}/drafts", json={
        "paper_id": test_paper_id,
        "answers": partial_answers,
        "time_used_seconds": 120,
        "current_index": 5
    }, timeout=10)
    
    if r.status_code == 200:
        log_pass(f"草稿保存成功 (Paper {test_paper_id})")
    else:
        log_fail(f"草稿保存失败: {r.status_code} - {r.text[:200]}")
    
    # Restore draft
    r = requests.get(f"{API}/drafts/{test_paper_id}", timeout=10)
    if r.status_code == 200:
        draft = r.json()
        if draft and draft.get("answers"):
            restored_count = len([a for a in draft["answers"] if a["user_answer"]])
            expected_count = len(questions) // 2
            if restored_count == expected_count:
                log_pass(f"草稿恢复成功: {restored_count}题已答")
            else:
                log_fail(f"草稿恢复数量不匹配: 期望{expected_count}, 实际{restored_count}")
        elif draft is None:
            log_fail("草稿恢复失败: 返回null")
        else:
            log_fail(f"草稿恢复失败: 无答案数据")
    else:
        log_fail(f"草稿恢复请求失败: {r.status_code}")
    
    # Delete draft
    r = requests.delete(f"{API}/drafts/{test_paper_id}", timeout=10)
    if r.status_code == 200:
        log_pass("草稿删除成功")
    else:
        log_fail(f"草稿删除失败: {r.status_code}")
    
    # Verify draft is gone
    r = requests.get(f"{API}/drafts/{test_paper_id}", timeout=10)
    if r.status_code == 200 and (r.json() is None or not r.json().get("answers")):
        log_pass("草稿已确认删除")
    else:
        log_fail("草稿删除后仍存在")
    
except Exception as e:
    log_fail(f"草稿测试异常: {e}")


# ========== Test 11: Attempt History ==========
section("Test 11: 考试记录列表")
try:
    r = requests.get(f"{API}/attempts?limit=100", timeout=10)
    if r.status_code == 200:
        attempts = r.json()
        log_pass(f"获取考试记录成功: {len(attempts)}条记录")
        
        # Verify attempt fields
        if attempts:
            required = ["id", "paper_id", "paper_title", "status", "score", "correct_count", "wrong_count", "unanswered"]
            for a in attempts[:3]:
                for field in required:
                    if field not in a:
                        log_fail(f"考试记录 {a.get('id', '?')} 缺少字段: {field}")
                        break
    else:
        log_fail(f"获取考试记录失败: {r.status_code}")
    
    # Test filter by paper_id
    r = requests.get(f"{API}/attempts?paper_id={test_paper_id}&limit=10", timeout=10)
    if r.status_code == 200:
        filtered = r.json()
        all_match = all(a["paper_id"] == test_paper_id for a in filtered)
        if all_match:
            log_pass(f"按试卷过滤记录成功: {len(filtered)}条")
        else:
            log_fail("按试卷过滤失败: 包含其他试卷记录")
    
except Exception as e:
    log_fail(f"考试记录测试异常: {e}")


# ========== Test 12: Attempt Detail ==========
section("Test 12: 考试记录详情")
try:
    r = requests.get(f"{API}/attempts?limit=1", timeout=10)
    if r.status_code == 200 and r.json():
        attempt_id = r.json()[0]["id"]
        
        r = requests.get(f"{API}/attempts/{attempt_id}", timeout=10)
        if r.status_code == 200:
            detail = r.json()
            required = ["attempt_id", "paper_id", "total_questions", "correct_count", "wrong_count", "unanswered", "score", "answers"]
            missing = [f for f in required if f not in detail]
            if missing:
                log_fail(f"考试记录详情缺少字段: {missing}")
            else:
                log_pass(f"考试记录详情获取成功: {len(detail['answers'])}题答题详情")
                
                # Verify each answer has required fields
                if detail["answers"]:
                    ans = detail["answers"][0]
                    ans_required = ["question_id", "question_number", "user_answer", "correct_answer", "is_correct", "stem", "options", "explanation"]
                    ans_missing = [f for f in ans_required if f not in ans]
                    if ans_missing:
                        log_fail(f"答题详情缺少字段: {ans_missing}")
                    else:
                        log_pass("答题详情字段完整")
        else:
            log_fail(f"获取考试记录详情失败: {r.status_code}")
    else:
        log_fail("无考试记录可测试")
except Exception as e:
    log_fail(f"考试记录详情测试异常: {e}")


# ========== Test 13: Edge Cases ==========
section("Test 13: 边界情况测试")

# Non-existent paper
try:
    r = requests.get(f"{API}/papers/99999", timeout=5)
    if r.status_code == 404:
        log_pass("不存在的试卷返回404")
    else:
        log_fail(f"不存在的试卷应返回404, 实际{r.status_code}")
except Exception as e:
    log_fail(f"边界测试异常: {e}")

# Non-existent attempt
try:
    r = requests.get(f"{API}/attempts/99999", timeout=5)
    if r.status_code == 404:
        log_pass("不存在的考试记录返回404")
    else:
        log_fail(f"不存在的考试记录应返回404, 实际{r.status_code}")
except Exception as e:
    log_fail(f"边界测试异常: {e}")

# Submit to non-existent paper
try:
    r = requests.post(f"{API}/attempts", json={
        "paper_id": 99999,
        "answers": [],
        "time_used_seconds": 0
    }, timeout=5)
    if r.status_code == 404:
        log_pass("提交不存在的试卷返回404")
    else:
        log_fail(f"提交不存在的试卷应返回404, 实际{r.status_code}")
except Exception as e:
    log_fail(f"边界测试异常: {e}")

# Draft for non-existent paper
try:
    r = requests.get(f"{API}/drafts/99999", timeout=5)
    if r.status_code == 200:
        log_pass("不存在试卷的草稿返回null")
    else:
        log_fail(f"不存在试卷的草稿应返回200+null, 实际{r.status_code}")
except Exception as e:
    log_fail(f"边界测试异常: {e}")

# Delete non-existent draft
try:
    r = requests.delete(f"{API}/drafts/99999", timeout=5)
    if r.status_code == 200:
        log_pass("删除不存在的草稿返回200")
    else:
        log_fail(f"删除不存在的草稿应返回200, 实际{r.status_code}")
except Exception as e:
    log_fail(f"边界测试异常: {e}")


# ========== Test 14: 2025 Papers Deep Validation ==========
section("Test 14: 2025年试卷深度验证")
for paper_id in [p["id"] for p in papers_2025]:
    try:
        # Get review mode
        r = requests.get(f"{API}/papers/{paper_id}/review", timeout=15)
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: review模式失败")
            continue
        
        data = r.json()
        questions = data["questions"]
        
        # Check question types
        types = {}
        for q in questions:
            t = q["question_type"]
            types[t] = types.get(t, 0) + 1
        
        log_info(f"Paper {paper_id} ({data['subject']}): {len(questions)}题 - {types}")
        
        # Verify each question
        issues = []
        for q in questions:
            # Check stem
            if not q["stem"] or len(q["stem"]) < 5:
                issues.append(f"Q{q['question_number']}: 题干为空或过短")
            
            # Check options
            opts = q["options"]
            if not isinstance(opts, dict) or len(opts) < 2:
                issues.append(f"Q{q['question_number']}: 选项无效")
            else:
                # Check option values
                for k, v in opts.items():
                    if not v or len(str(v)) < 1:
                        issues.append(f"Q{q['question_number']}: 选项{k}为空")
            
            # Check answer
            if not q["answer"]:
                issues.append(f"Q{q['question_number']}: 答案为空")
            else:
                # Verify answer keys exist in options
                for ans_char in q["answer"]:
                    if ans_char not in opts:
                        issues.append(f"Q{q['question_number']}: 答案{ans_char}不在选项中")
            
            # Check explanation
            if not q["explanation"]:
                issues.append(f"Q{q['question_number']}: 解析为空")
        
        if issues:
            for issue in issues[:5]:
                log_fail(f"  Paper {paper_id}: {issue}")
            if len(issues) > 5:
                log_fail(f"  ... 还有{len(issues)-5}个问题")
        else:
            log_pass(f"Paper {paper_id}: 所有题目验证通过")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: 深度验证异常: {e}")


# ========== Test 15: Answer Matching Accuracy ==========
section("Test 15: 答案匹配准确性验证")
for paper_id in [p["id"] for p in papers_2025]:
    try:
        r = requests.get(f"{API}/papers/{paper_id}/review", timeout=15)
        if r.status_code != 200:
            continue
        
        questions = r.json()["questions"]
        
        # Test: submit correct answers, verify each is marked correct
        answers = [{"question_id": q["id"], "user_answer": q["answer"]} for q in questions]
        
        r = requests.post(f"{API}/attempts", json={
            "paper_id": paper_id,
            "answers": answers,
            "time_used_seconds": 300
        }, timeout=15)
        
        if r.status_code != 200:
            log_fail(f"Paper {paper_id}: 答案匹配测试提交失败")
            continue
        
        result = r.json()
        
        # Check each answer result
        wrong_marked = 0
        for ans_result in result["answers"]:
            if ans_result["is_correct"] != True:
                wrong_marked += 1
                log_fail(f"  Q{ans_result['question_number']}: 正确答案被标记为错误 (user={ans_result['user_answer']}, correct={ans_result['correct_answer']})")
        
        if wrong_marked == 0:
            log_pass(f"Paper {paper_id}: 所有正确答案均被正确判分")
        else:
            log_fail(f"Paper {paper_id}: {wrong_marked}题被判错")
        
    except Exception as e:
        log_fail(f"Paper {paper_id}: 答案匹配测试异常: {e}")


# ========== Summary ==========
section("测试总结")
total = passed + failed
print(f"\n  总测试数: {total}")
print(f"  ✅ 通过: {passed}")
print(f"  ❌ 失败: {failed}")
print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "  无测试")

if errors:
    print(f"\n  失败列表:")
    for e in errors:
        print(f"    - {e}")

print()
sys.exit(0 if failed == 0 else 1)
