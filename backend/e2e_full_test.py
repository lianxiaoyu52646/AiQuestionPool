"""
E2E全方位测试 - 真题模考模块
仿真人答题，验证所有API和业务逻辑
"""
import requests
import json
import random
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/exam"

# 测试结果记录
test_results = []
bugs = []

def log_test(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "detail": detail})
    print(f"  {status}: {name}")
    if detail:
        print(f"    详情: {detail}")
    if not passed:
        bugs.append({"test": name, "detail": detail})

def api_get(path, expect_status=200):
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    r = requests.get(url, timeout=10)
    return r

def api_post(path, data, expect_status=200):
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    r = requests.post(url, json=data, timeout=10)
    return r

def api_delete(path, expect_status=200):
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    r = requests.delete(url, timeout=10)
    return r


def test_health():
    """测试0: 健康检查"""
    print("\n" + "="*60)
    print("测试0: 健康检查")
    print("="*60)
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    log_test("健康检查", r.status_code == 200, f"Status: {r.status_code}, Body: {r.text[:100]}")


def test_paper_list():
    """测试1: 获取试卷列表"""
    print("\n" + "="*60)
    print("测试1: 获取试卷列表")
    print("="*60)
    
    r = api_get("/papers")
    log_test("GET /papers 返回200", r.status_code == 200, f"Status: {r.status_code}")
    
    data = r.json()
    log_test("返回列表类型", isinstance(data, list) or isinstance(data, dict), f"Type: {type(data).__name__}")
    
    papers = data if isinstance(data, list) else data.get("items", data.get("papers", []))
    log_test("返回12张试卷", len(papers) == 12, f"实际: {len(papers)}")
    
    if papers:
        p = papers[0]
        required_fields = ["id", "title", "subject", "year"]
        for field in required_fields:
            log_test(f"试卷包含字段 '{field}'", field in p, f"keys: {list(p.keys())}")
        
        for p in papers:
            log_test(f"试卷{p.get('id')}标题非空", bool(p.get("title")), f"title: {p.get('title')}")
    
    return papers


def test_paper_detail(paper_id=1):
    """测试2: 获取试卷详情（考试模式，不含答案）"""
    print("\n" + "="*60)
    print(f"测试2: 获取试卷详情 (Paper {paper_id}) - 考试模式")
    print("="*60)
    
    r = api_get(f"/papers/{paper_id}")
    log_test(f"GET /papers/{paper_id} 返回200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code != 200:
        return None
    
    data = r.json()
    
    log_test("包含试卷标题", bool(data.get("title")), f"title: {data.get('title')}")
    log_test("包含题目总数", data.get("total_questions") == 120, f"total: {data.get('total_questions')}")
    
    questions = data.get("questions", [])
    log_test("返回120道题", len(questions) == 120, f"实际: {len(questions)}")
    
    if questions:
        q = questions[0]
        log_test("考试模式不返回answer", "answer" not in q or not q.get("answer"), 
                f"answer存在: {'answer' in q}, value: {q.get('answer', 'N/A')}")
        log_test("考试模式不返回explanation", "explanation" not in q or not q.get("explanation"),
                f"explanation存在: {'explanation' in q}")
        
        required_fields = ["id", "question_number", "question_type", "stem", "options"]
        for field in required_fields:
            log_test(f"题目包含字段 '{field}'", field in q, f"keys: {list(q.keys())[:10]}")
        
        options = q.get("options")
        log_test("选项非空", bool(options), f"options: {str(options)[:100]}")
    
    return data


def test_paper_review(paper_id=1):
    """测试3: 获取试卷详情（复习模式，含答案和解析）"""
    print("\n" + "="*60)
    print(f"测试3: 获取试卷复习模式 (Paper {paper_id})")
    print("="*60)
    
    r = api_get(f"/papers/{paper_id}/review")
    log_test(f"GET /papers/{paper_id}/review 返回200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code != 200:
        return None
    
    data = r.json()
    questions = data.get("questions", [])
    log_test("返回120道题", len(questions) == 120, f"实际: {len(questions)}")
    
    if questions:
        has_answer = any(q.get("answer") for q in questions)
        log_test("复习模式包含答案", has_answer, f"第一题answer: {questions[0].get('answer', 'N/A')}")
        
        has_explanation = any(q.get("explanation") for q in questions)
        log_test("复习模式包含解析", has_explanation, f"第一题explanation: {str(questions[0].get('explanation', 'N/A'))[:80]}")
    
    return data


def test_draft(paper_id=1):
    """测试4: 草稿功能"""
    print("\n" + "="*60)
    print(f"测试4: 草稿功能 (Paper {paper_id})")
    print("="*60)
    
    # 4.1 获取草稿（初始应为空或null）
    r = api_get(f"/drafts/{paper_id}")
    log_test("获取草稿(初始)", r.status_code in [200, 404], f"Status: {r.status_code}, body: {r.text[:100]}")
    
    # 4.2 保存草稿 (answers格式: [{question_id, user_answer}])
    draft_data = {
        "paper_id": paper_id,
        "answers": [
            {"question_id": 1, "user_answer": "A"},
            {"question_id": 2, "user_answer": "B"},
            {"question_id": 3, "user_answer": "C"}
        ]
    }
    r = api_post("/drafts", draft_data)
    log_test("保存草稿", r.status_code == 200, f"Status: {r.status_code}, Body: {r.text[:200]}")
    
    # 4.3 再次获取草稿
    r = api_get(f"/drafts/{paper_id}")
    log_test("获取已保存草稿", r.status_code == 200, f"Status: {r.status_code}")
    if r.status_code == 200:
        draft = r.json()
        answers = draft.get("answers", [])
        log_test("草稿包含3个答案", len(answers) == 3, f"answers: {answers}")
    
    # 4.4 更新草稿
    draft_data2 = {
        "paper_id": paper_id,
        "answers": [
            {"question_id": 1, "user_answer": "D"},
            {"question_id": 2, "user_answer": "E"},
            {"question_id": 3, "user_answer": "A"},
            {"question_id": 4, "user_answer": "B"},
            {"question_id": 5, "user_answer": "C"}
        ]
    }
    r = api_post("/drafts", draft_data2)
    log_test("更新草稿", r.status_code == 200, f"Status: {r.status_code}")
    
    # 4.5 验证更新
    r = api_get(f"/drafts/{paper_id}")
    if r.status_code == 200:
        draft = r.json()
        answers = draft.get("answers", [])
        log_test("草稿已更新为5个答案", len(answers) == 5, f"answers count: {len(answers)}")
        # 查找question_id=1的答案
        q1_answer = next((a.get("user_answer") for a in answers if a.get("question_id") == 1), None)
        log_test("草稿Q1答案已更新为D", q1_answer == "D", f"Q1: {q1_answer}")
    
    # 4.6 删除草稿
    r = api_delete(f"/drafts/{paper_id}")
    log_test("删除草稿", r.status_code == 200, f"Status: {r.status_code}")
    
    # 4.7 验证已删除 (API返回null+200表示无草稿)
    r = api_get(f"/drafts/{paper_id}")
    is_deleted = r.status_code == 200 and (r.json() is None or r.json() == {})
    log_test("草稿已删除", is_deleted, f"Status: {r.status_code}, body: {r.text[:100]}")


def test_submit_exam(paper_id=1, review_data=None):
    """测试5: 仿真答题 - 提交答卷"""
    print("\n" + "="*60)
    print(f"测试5: 仿真答题 (Paper {paper_id})")
    print("="*60)
    
    if not review_data:
        print("  ⚠️ 无复习数据，跳过")
        return None
    
    questions = review_data.get("questions", [])
    
    # === 场景A: 全部正确答题 ===
    print("\n  --- 场景A: 全部正确答题 ---")
    correct_answers = []
    for q in questions:
        correct_answers.append({"question_id": q["id"], "user_answer": q["answer"]})
    
    submit_data = {
        "paper_id": paper_id,
        "answers": correct_answers
    }
    
    r = api_post("/attempts", submit_data)
    log_test("提交全对答卷", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        result = r.json()
        log_test("全对-得分120", result.get("score") == 120, 
                f"score: {result.get('score')}")
        log_test("全对-正确数120", result.get("correct_count") == 120,
                f"correct: {result.get('correct_count')}")
        log_test("全对-错误数0", result.get("wrong_count") == 0,
                f"wrong: {result.get('wrong_count')}")
        log_test("全对-未答数0", result.get("unanswered") == 0,
                f"unanswered: {result.get('unanswered')}")
        log_test("全对-通过", result.get("passed") == True,
                f"passed: {result.get('passed')}")
        
        attempt_id_a = result.get("attempt_id")
        
        answers = result.get("answers", [])
        log_test("返回答题详情", len(answers) == 120, f"answers count: {len(answers)}")
        if answers:
            log_test("每题标记正确", all(a.get("is_correct") == True for a in answers),
                    f"first is_correct: {answers[0].get('is_correct')}")
    
    # === 场景B: 全部错误答题 ===
    print("\n  --- 场景B: 全部错误答题 ---")
    wrong_answers = []
    for q in questions:
        correct = q["answer"]
        if len(correct) == 1:
            wrong = chr(ord("A") + ((ord(correct) - ord("A") + 1) % 5))
        else:
            wrong = "X"
        wrong_answers.append({"question_id": q["id"], "user_answer": wrong})
    
    submit_data2 = {
        "paper_id": paper_id,
        "answers": wrong_answers
    }
    
    r = api_post("/attempts", submit_data2)
    log_test("提交全错答卷", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        result = r.json()
        log_test("全错-得分0", result.get("score") == 0,
                f"score: {result.get('score')}")
        log_test("全错-正确数0", result.get("correct_count") == 0,
                f"correct: {result.get('correct_count')}")
        log_test("全错-错误数120", result.get("wrong_count") == 120,
                f"wrong: {result.get('wrong_count')}")
    
    # === 场景C: 部分答题（只答60题） ===
    print("\n  --- 场景C: 部分答题(60题) ---")
    partial_answers = []
    for q in questions[:60]:
        partial_answers.append({"question_id": q["id"], "user_answer": q["answer"]})
    
    submit_data3 = {
        "paper_id": paper_id,
        "answers": partial_answers
    }
    
    r = api_post("/attempts", submit_data3)
    log_test("提交部分答卷", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        result = r.json()
        log_test("部分答-得分60", result.get("score") == 60,
                f"score: {result.get('score')}")
        log_test("部分答-正确数60", result.get("correct_count") == 60,
                f"correct: {result.get('correct_count')}")
        log_test("部分答-未答数60", result.get("unanswered") == 60,
                f"unanswered: {result.get('unanswered')}")
    
    # === 场景D: 空答卷 ===
    print("\n  --- 场景D: 空答卷 ---")
    submit_data4 = {
        "paper_id": paper_id,
        "answers": []
    }
    
    r = api_post("/attempts", submit_data4)
    log_test("提交空答卷", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        result = r.json()
        log_test("空答-得分0", result.get("score") == 0,
                f"score: {result.get('score')}")
        log_test("空答-未答数120", result.get("unanswered") == 120,
                f"unanswered: {result.get('unanswered')}")
    
    # === 场景E: 仿真随机答题 ===
    print("\n  --- 场景E: 仿真随机答题(模拟真实考生) ---")
    random.seed(42)
    random_answers = []
    for q in questions:
        if random.random() < 0.7:
            correct = q["answer"]
            if random.random() < 0.6:
                random_answers.append({"question_id": q["id"], "user_answer": correct})
            else:
                options = q.get("options", {})
                if isinstance(options, str):
                    try:
                        options = json.loads(options)
                    except:
                        options = {}
                if isinstance(options, dict) and len(options) > 0:
                    keys = list(options.keys())
                    wrong_keys = [k for k in keys if k not in correct]
                    if wrong_keys:
                        random_answers.append({"question_id": q["id"], "user_answer": random.choice(wrong_keys)})
                    else:
                        random_answers.append({"question_id": q["id"], "user_answer": correct})
                else:
                    random_answers.append({"question_id": q["id"], "user_answer": "A"})
    
    submit_data5 = {
        "paper_id": paper_id,
        "answers": random_answers
    }
    
    r = api_post("/attempts", submit_data5)
    log_test("提交随机答卷", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        result = r.json()
        answered = len(random_answers)
        log_test("随机答-已答数一致", result.get("total_answered") == answered,
                f"answered: {result.get('total_answered')}, expected: {answered}")
        log_test("随机答-未答数=120-已答", result.get("unanswered") == 120 - answered,
                f"unanswered: {result.get('unanswered')}, expected: {120 - answered}")
        score = result.get("score", 0)
        correct = result.get("correct_count", 0)
        log_test("随机答-得分=正确数", score == correct,
                f"score: {score}, correct: {correct}")
        log_test("随机答-正确+错误+未答=120", 
                result.get("correct_count", 0) + result.get("wrong_count", 0) + result.get("unanswered", 0) == 120,
                f"correct: {result.get('correct_count')}, wrong: {result.get('wrong_count')}, unanswered: {result.get('unanswered')}")
        
        return result.get("attempt_id")
    
    return None


def test_attempt_list(paper_id=1):
    """测试6: 获取考试记录列表"""
    print("\n" + "="*60)
    print(f"测试6: 获取考试记录列表")
    print("="*60)
    
    r = api_get("/attempts")
    log_test("GET /attempts 返回200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        attempts = data if isinstance(data, list) else data.get("items", [])
        log_test("返回考试记录列表", len(attempts) > 0, f"记录数: {len(attempts)}")
        
        if attempts:
            a = attempts[0]
            required_fields = ["id", "paper_id", "score", "status"]
            for field in required_fields:
                log_test(f"记录包含字段 '{field}'", field in a, f"keys: {list(a.keys())[:15]}")
            log_test("记录包含paper_title", "paper_title" in a, f"paper_title: {a.get('paper_title', 'N/A')}")
    
    r = api_get(f"/attempts?paper_id={paper_id}")
    log_test(f"按paper_id={paper_id}过滤", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        attempts = data if isinstance(data, list) else data.get("items", [])
        log_test("过滤结果正确", all(a.get("paper_id") == paper_id for a in attempts),
                f"paper_ids: {[a.get('paper_id') for a in attempts[:5]]}")


def test_attempt_detail(attempt_id):
    """测试7: 获取考试记录详情"""
    print("\n" + "="*60)
    print(f"测试7: 获取考试记录详情 (Attempt {attempt_id})")
    print("="*60)
    
    r = api_get(f"/attempts/{attempt_id}")
    log_test(f"GET /attempts/{attempt_id} 返回200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        log_test("包含得分", "score" in data, f"score: {data.get('score')}")
        log_test("包含attempt_id", "attempt_id" in data, f"attempt_id: {data.get('attempt_id')}")
        log_test("包含passed字段", "passed" in data, f"passed: {data.get('passed')}")
        
        answers = data.get("answers", [])
        log_test("包含答题详情", len(answers) > 0, f"answers count: {len(answers)}")
        
        if answers:
            a = answers[0]
            required_fields = ["question_id", "user_answer", "is_correct", "correct_answer", "explanation"]
            for field in required_fields:
                log_test(f"答题记录包含字段 '{field}'", field in a, f"keys: {list(a.keys())[:15]}")


def test_multi_paper(review_data_by_paper):
    """测试8: 多试卷测试"""
    print("\n" + "="*60)
    print("测试8: 多试卷测试")
    print("="*60)
    
    for paper_id, review_data in review_data_by_paper.items():
        print(f"\n  --- Paper {paper_id} ---")
        questions = review_data.get("questions", [])
        
        correct_answers = []
        for q in questions:
            correct_answers.append({"question_id": q["id"], "user_answer": q["answer"]})
        
        r = api_post("/attempts", {"paper_id": paper_id, "answers": correct_answers})
        log_test(f"Paper {paper_id} 提交全对答卷", r.status_code == 200, f"Status: {r.status_code}")
        
        if r.status_code == 200:
            result = r.json()
            log_test(f"Paper {paper_id} 全对得分120", result.get("score") == 120,
                    f"score: {result.get('score')}")
            log_test(f"Paper {paper_id} 正确数120", result.get("correct_count") == 120,
                    f"correct: {result.get('correct_count')}")


def test_x_type_questions(review_data):
    """测试9: X型多选题判分逻辑"""
    print("\n" + "="*60)
    print("测试9: X型多选题判分逻辑")
    print("="*60)
    
    questions = review_data.get("questions", [])
    x_questions = [q for q in questions if q.get("question_type") == "X"]
    
    if not x_questions:
        log_test("无X型题", True, "跳过")
        return
    
    log_test(f"找到X型题", len(x_questions) > 0, f"数量: {len(x_questions)}")
    
    q = x_questions[0]
    qid = q["id"]
    correct = q["answer"]
    
    if len(correct) > 1:
        shuffled = correct[::-1]
        r = api_post("/attempts", {"paper_id": 1, "answers": [{"question_id": qid, "user_answer": shuffled}]})
        if r.status_code == 200:
            result = r.json()
            answers = result.get("answers", [])
            # 按question_id查找对应的答题记录（不能使用answers[0]，因为answers按题号排序）
            target = next((a for a in answers if a.get("question_id") == qid), None)
            if target:
                log_test("X型题答案顺序不影响判分", target.get("is_correct") == True,
                        f"correct_answer: {correct}, submitted: {shuffled}, is_correct: {target.get('is_correct')}")
            else:
                log_test("X型题答案顺序不影响判分", False, f"未找到question_id={qid}的答题记录")
    
    if len(correct) > 1:
        partial = correct[0]
        r = api_post("/attempts", {"paper_id": 1, "answers": [{"question_id": qid, "user_answer": partial}]})
        if r.status_code == 200:
            result = r.json()
            answers = result.get("answers", [])
            target = next((a for a in answers if a.get("question_id") == qid), None)
            if target:
                log_test("X型题部分正确判错", target.get("is_correct") == False,
                        f"correct: {correct}, submitted: {partial}, is_correct: {target.get('is_correct')}")
            else:
                log_test("X型题部分正确判错", False, f"未找到question_id={qid}的答题记录")


def test_edge_cases():
    """测试10: 边界情况"""
    print("\n" + "="*60)
    print("测试10: 边界情况")
    print("="*60)
    
    r = api_get("/papers/999")
    log_test("获取不存在的试卷", r.status_code == 404, f"Status: {r.status_code}")
    
    r = api_get("/attempts/99999")
    log_test("获取不存在的考试记录", r.status_code == 404, f"Status: {r.status_code}")
    
    r = api_post("/attempts", {"paper_id": 999, "answers": []})
    log_test("提交无效paper_id", r.status_code in [404, 400], f"Status: {r.status_code}")
    
    r = api_get("/drafts/999")
    log_test("获取不存在的草稿", r.status_code in [200, 404], f"Status: {r.status_code}, body: {r.text[:80]}")
    
    r = api_delete("/drafts/999")
    log_test("删除不存在的草稿", r.status_code in [404, 200], f"Status: {r.status_code}")


def test_pass_score(paper_id=1, review_data=None):
    """测试11: 合格分数线验证"""
    print("\n" + "="*60)
    print(f"测试11: 合格分数线验证 (Paper {paper_id})")
    print("="*60)
    
    if not review_data:
        return
    
    questions = review_data.get("questions", [])
    pass_score = review_data.get("pass_score", 72)
    log_test("合格分数线为72", pass_score == 72, f"pass_score: {pass_score}")
    
    answers_72 = []
    for q in questions[:72]:
        answers_72.append({"question_id": q["id"], "user_answer": q["answer"]})
    
    r = api_post("/attempts", {"paper_id": paper_id, "answers": answers_72})
    if r.status_code == 200:
        result = r.json()
        log_test("答对72题得分72", result.get("score") == 72, f"score: {result.get('score')}")
    
    answers_71 = []
    for q in questions[:71]:
        answers_71.append({"question_id": q["id"], "user_answer": q["answer"]})
    
    r = api_post("/attempts", {"paper_id": paper_id, "answers": answers_71})
    if r.status_code == 200:
        result = r.json()
        log_test("答对71题得分71", result.get("score") == 71, f"score: {result.get('score')}")


def test_study_module():
    """测试12: 学习模块基本功能"""
    print("\n" + "="*60)
    print("测试12: 学习模块基本功能")
    print("="*60)
    
    r = requests.get(f"{BASE_URL}/api/study/queue", timeout=10)
    log_test("GET /study/queue", r.status_code == 200, f"Status: {r.status_code}")
    
    r = requests.get(f"{BASE_URL}/api/study/due-count", timeout=10)
    log_test("GET /study/due-count", r.status_code == 200, f"Status: {r.status_code}")
    
    r = requests.get(f"{BASE_URL}/api/study/stats", timeout=10)
    log_test("GET /study/stats", r.status_code == 200, f"Status: {r.status_code}")
    
    r = requests.get(f"{BASE_URL}/api/study/wrong-questions", timeout=10)
    log_test("GET /study/wrong-questions", r.status_code == 200, f"Status: {r.status_code}")


def test_questions_module():
    """测试13: 题库模块基本功能"""
    print("\n" + "="*60)
    print("测试13: 题库模块基本功能")
    print("="*60)
    
    r = requests.get(f"{BASE_URL}/api/questions/list?page=1&size=5", timeout=10)
    log_test("GET /questions/list", r.status_code == 200, f"Status: {r.status_code}")
    
    r = requests.get(f"{BASE_URL}/api/questions/categories/list", timeout=10)
    log_test("GET /questions/categories/list", r.status_code == 200, f"Status: {r.status_code}")


def test_tags_module():
    """测试14: 标签模块基本功能"""
    print("\n" + "="*60)
    print("测试14: 标签模块基本功能")
    print("="*60)
    
    r = requests.get(f"{BASE_URL}/api/tags/list", timeout=10)
    log_test("GET /tags/list", r.status_code == 200, f"Status: {r.status_code}")


def generate_report():
    """生成测试报告"""
    print("\n" + "="*60)
    print("E2E测试报告")
    print("="*60)
    
    total = len(test_results)
    passed = sum(1 for t in test_results if t["passed"])
    failed = sum(1 for t in test_results if not t["passed"])
    
    print(f"\n总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%" if total > 0 else "N/A")
    
    if bugs:
        print(f"\n{'='*60}")
        print(f"发现的Bug ({len(bugs)}个):")
        print(f"{'='*60}")
        for i, bug in enumerate(bugs, 1):
            print(f"\n  Bug {i}: {bug['test']}")
            print(f"    详情: {bug['detail']}")
    else:
        print(f"\n✅ 未发现Bug!")
    
    return failed


def main():
    print("="*60)
    print("E2E全方位测试 - 真题模考模块")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    test_health()
    papers = test_paper_list()
    exam_data = test_paper_detail(paper_id=1)
    review_data = test_paper_review(paper_id=1)
    test_draft(paper_id=1)
    attempt_id = test_submit_exam(paper_id=1, review_data=review_data)
    test_attempt_list(paper_id=1)
    if attempt_id:
        test_attempt_detail(attempt_id)
    
    print("\n  获取多张试卷复习数据...")
    review_data_by_paper = {1: review_data}
    for pid in [5, 9]:
        r = api_get(f"/papers/{pid}/review")
        if r.status_code == 200:
            review_data_by_paper[pid] = r.json()
        time.sleep(0.5)
    test_multi_paper(review_data_by_paper)
    
    test_x_type_questions(review_data)
    test_edge_cases()
    test_pass_score(paper_id=1, review_data=review_data)
    test_study_module()
    test_questions_module()
    test_tags_module()
    
    failed = generate_report()
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return failed

if __name__ == "__main__":
    failed = main()
    sys.exit(failed)
