# -*- coding: utf-8 -*-
"""爬取 hqwx.com 题库 API - 中药一模拟试卷"""
import sys
import os
import json
import re
import time
import requests
from html import unescape

# 设置 stdout 编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加 backend 目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.exam_models import ExamPaper, ExamQuestion, Base

# API 配置
PASSPORT = "342b31763b699d59db66743e6e14628d41a6d7ae83d39f17e6779dd71706f5dd735a536533a4f2db0c04645d629d7f97e21dab56b39074a0b1854264e85e146bcac461e89ed5604747229e9cc2f69d41ef"
TOKEN = PASSPORT
BOX_ID = 3796

# 3套试卷信息
PAPERS = [
    {"paperId": 4812, "title": "中药一-摸底测评100题", "boxId": 3796},
    {"paperId": 38540, "title": "2026年-中药学专业知识（一）-模拟试卷（一）", "boxId": 3796},
    {"paperId": 82958, "title": "2026年-中药学专业知识（一）-模拟试卷（二）", "boxId": 3796},
]

# 通用请求参数
COMMON_PARAMS = {
    "_appid": "wwwedu24ol",
    "appid": "wwwedu24ol",
    "_org_id": "2",
    "org_id": "2",
    "_os": "3",
    "os": "3",
    "_v": "1.0.0",
    "v": "1.0.0",
    "schId": "2",
    "pschId": "14",
    "platform": "web",
    "edu24ol_token": TOKEN,
    "passport": PASSPORT,
}


def strip_html(text):
    """去除 HTML 标签，保留纯文本（img标签替换为[图片]）"""
    if not text:
        return ""
    # 循环处理：先 unescape HTML 实体，再去标签，重复直到稳定
    for _ in range(3):
        text = unescape(text)
        # 将 img 标签替换为 [图片] 占位符
        text = re.sub(r'<img[^>]*/?>', '[图片]', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_paper_info(paper_id, box_id):
    """调用 getPaper API 获取试卷信息和题目ID列表"""
    url = "https://japi.hqwx.com/paper/getPaper"
    data = {
        **COMMON_PARAMS,
        "paperId": paper_id,
        "boxId": box_id,
    }
    resp = requests.post(url, data=data, timeout=30)
    result = resp.json()
    
    if result.get("status", {}).get("code") != 0:
        print(f"  ✗ getPaper 失败: {result.get('status', {}).get('msg')}")
        return None
    
    return result["data"]


def extract_question_ids(paper_data):
    """从 getPaper 响应中提取所有题目ID"""
    question_ids = []
    paper_info = paper_data.get("paperInfo", {})
    question_list = paper_data.get("questionList", {})
    group_list = question_list.get("groupList", [])
    
    for group in group_list:
        questions = group.get("questionList", [])
        for q in questions:
            qid = q.get("id")
            if qid:
                question_ids.append(qid)
            # 也检查 topicList 中的子题
            # topic_list 中的 id 是 topic_id，不是 question_id
    
    return question_ids


def get_question_list(question_ids):
    """调用 get_question_list API 获取完整题目数据"""
    url = "https://tikuapi.hqwx.com/qbox_api/v1/question/get_question_list"
    ids_str = ",".join(str(qid) for qid in question_ids)
    data = {
        **COMMON_PARAMS,
        "question_ids": ids_str,
    }
    resp = requests.post(url, data=data, timeout=30)
    result = resp.json()
    
    if result.get("status", {}).get("code") != 0:
        print(f"  ✗ get_question_list 失败: {result.get('status', {}).get('msg')}")
        return None
    
    return result["data"]


def fetch_js_content(url):
    """从JS URL获取内容（getNoteDataCallBackJs格式），保留换行符"""
    if not url or not url.startswith("http"):
        return ""
    try:
        resp = requests.get(url, timeout=10)
        text = resp.text
        # JS格式: getNoteDataCallBackJs("id", "HTML内容")
        m = re.search(r'getNoteDataCallBackJs\("[^"]+","(.+)"\)', text, re.DOTALL)
        if m:
            html_content = m.group(1)
            # 先 unescape HTML 实体（JS内容是双重转义的）
            html_content = unescape(html_content)
            # 把块级标签替换为换行
            html_content = re.sub(r'</?p[^>]*>', '\n', html_content)
            html_content = re.sub(r'<br\s*/?>', '\n', html_content)
            # 再 unescape + 去标签（保留 img 为 [图片]）
            for _ in range(2):
                html_content = unescape(html_content)
                html_content = re.sub(r'<img[^>]*/?>', '[图片]', html_content, flags=re.IGNORECASE)
                html_content = re.sub(r'<[^>]+>', '', html_content)
            # 只去除行首尾空白和多余空行，保留换行
            lines = [l.strip() for l in html_content.split('\n')]
            html_content = '\n'.join(l for l in lines if l)
            return html_content
        # 兜底
        return strip_html(text)
    except Exception as e:
        return f""


def parse_options_from_text(text):
    """从纯文本中解析A-E选项"""
    if not text:
        return {}
    options = {}
    # 先尝试按行分割（每行一个选项）
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        m = re.match(r'^([A-E])[．.、\s]+(.+)', line)
        if m:
            val = m.group(2).strip()
            # 避免贪婪匹配把后续选项也吃进去（如 "A.B.C.D.E." 应该得到 A=''）
            # 检查 val 是否以 B. C. 等开头
            rest = re.match(r'^([B-E])[．.、\s]+(.+)', val)
            if rest:
                # val 实际上是空的（选项内容为空）
                options[m.group(1)] = ''
            else:
                options[m.group(1)] = val
    # 如果按行解析的结果不完整（少于2个），用 findall 在整段文本中匹配
    # 匹配 "A．选项内容" 直到下一个 "B．" 或行尾（处理无换行的情况）
    if len(options) < 2:
        matches = re.findall(r'([A-E])[．.、\s]+(.+?)(?=\s*[A-E][．.、\s]|$)', text)
        if len(matches) > len(options):
            options = {}
            for key, val in matches:
                options[key] = val.strip()
    return options


def parse_question(q_data, question_number, group_id=None, shared_stem=None):
    """解析单道题目数据（A型/X型题，每个question只有1个topic）"""
    qtype = q_data.get("qtype", 0)
    is_multi = q_data.get("is_multi", 0)
    qtype_alias = q_data.get("qtype_alias", "")
    
    # 确定题型代码
    if is_multi == 1 or qtype == 1:
        q_type_code = "X"  # 多项选择题
    elif "B" in qtype_alias:
        q_type_code = "B"  # 配伍选择题
    elif "C" in qtype_alias or "A3" in qtype_alias:
        q_type_code = "C"  # 综合分析选择题
    else:
        q_type_code = "A"  # 最佳选择题
    
    topic_list = q_data.get("topic_list", [])
    if not topic_list:
        return None
    
    topic = topic_list[0]
    
    # 题干内容
    content = topic.get("content", "")
    stem_text = strip_html(content)
    
    # 如果题干为空，尝试从 content JS URL 获取
    if not stem_text and content.startswith("http"):
        stem_text = fetch_js_content(content)
    
    # 如果题干仍为空，使用 title
    if not stem_text:
        stem_text = strip_html(q_data.get("title", ""))
    
    # 答案
    answer = topic.get("answer_option", "")
    
    # 选项
    options = {}
    option_list = topic.get("option_list", [])
    for opt in option_list:
        seq = opt.get("seq", "")
        opt_content = strip_html(opt.get("content", ""))
        if seq:
            options[seq] = opt_content
    
    # 如果选项内容为空，尝试从 content JS URL 获取（A型/X型题的选项也可能在JS中）
    if all(not v for v in options.values()):
        content_url = q_data.get("content", "")
        if content_url and content_url.startswith("http"):
            js_text = fetch_js_content(content_url)
            if js_text:
                parsed_opts = parse_options_from_text(js_text)
                if parsed_opts:
                    options = parsed_opts
    
    # 解析 (analysis_text 是一个URL，指向JS文件)
    analysis_url = topic.get("analysis_text", "")
    
    return {
        "question_number": question_number,
        "question_type": q_type_code,
        "stem": stem_text,
        "options": options,
        "answer": answer,
        "explanation": f"解析链接: {analysis_url}" if analysis_url else "",
        "group_id": group_id,
        "shared_stem": shared_stem,
    }


def parse_b_type_question(q_data, start_number, group_id=None):
    """解析B型题（配伍选择题），返回多个子题列表
    
    B型题特点:
    - title 字段可能包含共享选项文本（但不完整）
    - content 字段是JS URL，包含完整的共享选项
    - topic_list 有多个子题，每个子题有自己的 content(题干) 和 answer_option(答案)
    - option_list 中的 content 为空（选项是共享的，存在JS中）
    """
    topic_list = q_data.get("topic_list", [])
    if not topic_list:
        return []
    
    # 从 content JS URL 获取共享选项
    content_url = q_data.get("content", "")
    shared_options = {}
    shared_stem_text = ""
    if content_url and content_url.startswith("http"):
        js_text = fetch_js_content(content_url)
        if js_text:
            shared_options = parse_options_from_text(js_text)
            shared_stem_text = js_text  # 保存完整选项文本作为 shared_stem
    
    # 如果JS没获取到选项，尝试从 title 解析
    if not shared_options:
        title_text = strip_html(q_data.get("title", ""))
        # 去掉 title 中的非选项前缀（如 "模拟卷3-" 或 "2016中药一模考试题一配伍选择题"）
        shared_options = parse_options_from_text(title_text)
        if shared_options:
            shared_stem_text = title_text
    
    # 如果还是没有选项，用 title 作为 shared_stem
    if not shared_stem_text:
        shared_stem_text = strip_html(q_data.get("title", ""))
    
    parsed_questions = []
    for i, topic in enumerate(topic_list):
        q_num = start_number + i
        
        # 子题题干
        content = topic.get("content", "")
        stem_text = strip_html(content)
        if not stem_text and content.startswith("http"):
            stem_text = fetch_js_content(content)
        
        # 答案
        answer = topic.get("answer_option", "")
        
        # 解析
        analysis_url = topic.get("analysis_text", "")
        
        parsed_questions.append({
            "question_number": q_num,
            "question_type": "B",
            "stem": stem_text,
            "options": shared_options.copy(),
            "answer": answer,
            "explanation": f"解析链接: {analysis_url}" if analysis_url else "",
            "group_id": group_id,
            "shared_stem": shared_stem_text if shared_stem_text else None,
        })
    
    return parsed_questions


def parse_c_type_question(q_data, start_number, group_id=None):
    """解析C型题（综合分析题），返回多个子题列表
    
    C型题特点:
    - title 字段包含共享题干文本（如案例描述）
    - content 字段是JS URL，包含完整的共享题干
    - topic_list 有多个子题，每个子题有自己的 content(题干) 和 answer_option(答案)
    - option_list 中的 content 有内容（每个子题有自己的选项，与B型题不同）
    """
    topic_list = q_data.get("topic_list", [])
    if not topic_list:
        return []
    
    # 获取共享题干：优先从 content JS URL 获取，其次从 title 获取
    content_url = q_data.get("content", "")
    shared_stem_text = ""
    if content_url and content_url.startswith("http"):
        js_text = fetch_js_content(content_url)
        if js_text:
            shared_stem_text = js_text
    if not shared_stem_text:
        shared_stem_text = strip_html(q_data.get("title", ""))
    
    parsed_questions = []
    for i, topic in enumerate(topic_list):
        q_num = start_number + i
        
        # 子题题干
        content = topic.get("content", "")
        stem_text = strip_html(content)
        if not stem_text and content.startswith("http"):
            stem_text = fetch_js_content(content)
        
        # 答案
        answer = topic.get("answer_option", "")
        
        # 选项：C型题每个子题有自己的 option_list，且 content 有内容
        options = {}
        option_list = topic.get("option_list", [])
        for opt in option_list:
            seq = opt.get("seq", "")
            opt_content = strip_html(opt.get("content", ""))
            if seq:
                options[seq] = opt_content
        
        # 如果选项内容为空，尝试从 content JS URL 获取
        if all(not v for v in options.values()):
            topic_content_url = topic.get("content", "")
            if topic_content_url and topic_content_url.startswith("http"):
                js_text = fetch_js_content(topic_content_url)
                if js_text:
                    parsed_opts = parse_options_from_text(js_text)
                    if parsed_opts:
                        options = parsed_opts
        
        # 解析
        analysis_url = topic.get("analysis_text", "")
        
        parsed_questions.append({
            "question_number": q_num,
            "question_type": "C",
            "stem": stem_text,
            "options": options,
            "answer": answer,
            "explanation": f"解析链接: {analysis_url}" if analysis_url else "",
            "group_id": group_id,
            "shared_stem": shared_stem_text if shared_stem_text else None,
        })
    
    return parsed_questions


def fetch_analysis_text(url):
    """获取解析文本（从JS文件中）"""
    if not url or not url.startswith("http"):
        return ""
    try:
        resp = requests.get(url, timeout=10)
        text = resp.text
        # JS文件中可能包含解析文本，尝试提取
        # 去除JS代码，保留文本
        text = re.sub(r'document\.write\(', '', text)
        text = re.sub(r'\);?\s*$', '', text)
        text = unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.strip().strip('"').strip("'")
        return text
    except Exception as e:
        return f"解析获取失败: {e}"


def crawl_paper(paper_info):
    """爬取一套试卷的完整数据"""
    paper_id = paper_info["paperId"]
    box_id = paper_info["boxId"]
    title = paper_info["title"]
    
    print(f"\n{'='*60}")
    print(f"正在爬取: {title} (paperId={paper_id})")
    print(f"{'='*60}")
    
    # 1. 获取试卷信息
    print("  [1/3] 获取试卷信息...")
    paper_data = get_paper_info(paper_id, box_id)
    if not paper_data:
        return None
    
    paper_info_data = paper_data.get("paperInfo", {})
    total = paper_info_data.get("total", 0)
    answer_time = paper_info_data.get("answerTime", 120)
    paper_score = paper_info_data.get("paperScore", 100)
    pass_score = paper_info_data.get("paperPassScore", 60)
    paper_year = paper_info_data.get("paperYear", 2026)
    
    print(f"  试卷: {paper_info_data.get('title', title)}")
    print(f"  题目数: {total}, 时长: {answer_time}分钟, 总分: {paper_score}, 合格: {pass_score}")
    
    # 2. 提取题目ID
    print("  [2/3] 提取题目ID...")
    question_ids = extract_question_ids(paper_data)
    print(f"  共 {len(question_ids)} 道题目")
    
    if not question_ids:
        print("  ✗ 未找到题目ID")
        return None
    
    # 3. 获取题目详情
    print("  [3/3] 获取题目详情...")
    questions_data = get_question_list(question_ids)
    if not questions_data:
        return None
    
    # questions_data 是一个列表
    # 构建题目ID到数据的映射
    q_data_map = {}
    for q in questions_data:
        q_data_map[q["id"]] = q
    
    # 按照试卷中的顺序解析题目
    parsed_questions = []
    question_number = 0
    
    question_list = paper_data.get("questionList", {})
    group_list = question_list.get("groupList", [])
    
    for group in group_list:
        group_name = group.get("groupName", "")
        group_id = str(group.get("id", ""))
        group_questions = group.get("questionList", [])
        
        # 检查是否是案例分析题组（有共享题干）
        is_case_group = "案例" in group_name or "综合" in group_name or "共用题干" in group_name
        
        for q in group_questions:
            qid = q.get("id")
            if qid and qid in q_data_map:
                q_data = q_data_map[qid]
                qtype = q_data.get("qtype", 0)
                qtype_alias = q_data.get("qtype_alias", "") or ""
                is_c_type = "C" in qtype_alias or "A3" in qtype_alias
                # B型题：alias含"B"，或 qtype=6 但不是C型题（有些配伍选择题缺失alias）
                is_b_type = "B" in qtype_alias or (qtype == 6 and not is_c_type)
                
                if is_b_type:
                    # B型题（配伍选择题）：展开为多个子题
                    sub_questions = parse_b_type_question(q_data, question_number + 1, group_id)
                    if sub_questions:
                        parsed_questions.extend(sub_questions)
                        question_number += len(sub_questions)
                        if question_number % 20 == 0 or question_number >= len(question_ids):
                            print(f"    已解析 {question_number} 题...")
                elif is_c_type:
                    # C型题（综合分析题）：展开为多个子题，每个子题有自己的选项
                    sub_questions = parse_c_type_question(q_data, question_number + 1, group_id)
                    if sub_questions:
                        parsed_questions.extend(sub_questions)
                        question_number += len(sub_questions)
                        if question_number % 20 == 0 or question_number >= len(question_ids):
                            print(f"    已解析 {question_number} 题...")
                else:
                    # A型/X型题：单道题
                    question_number += 1
                    shared_stem = None
                    if is_case_group:
                        shared_stem = group_name
                    
                    parsed = parse_question(q_data, question_number, group_id, shared_stem)
                    if parsed:
                        parsed_questions.append(parsed)
                        if question_number % 20 == 0:
                            print(f"    已解析 {question_number} 题...")
    
    print(f"  ✓ 共解析 {len(parsed_questions)} 道题目")
    
    # 统计题型
    type_counts = {}
    for q in parsed_questions:
        t = q["question_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"  题型分布: {type_counts}")
    
    return {
        "paper_info": {
            "title": title,
            "year": paper_year,
            "total_questions": len(parsed_questions),
            "time_limit_minutes": answer_time,
            "pass_score": int(pass_score),
            "subject": "中药学专业知识（一）",
            "description": paper_info_data.get("remark", ""),
        },
        "questions": parsed_questions,
    }


def import_to_db(crawled_data):
    """将爬取的数据导入数据库"""
    print(f"\n{'='*60}")
    print(f"导入数据库: {crawled_data['paper_info']['title']}")
    print(f"{'='*60}")
    
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = db.query(ExamPaper).filter(
            ExamPaper.title == crawled_data["paper_info"]["title"]
        ).first()
        
        if existing:
            print(f"  试卷已存在 (id={existing.id})，删除旧数据...")
            db.delete(existing)
            db.commit()
        
        # 创建试卷
        pi = crawled_data["paper_info"]
        paper = ExamPaper(
            subject=pi["subject"],
            year=pi["year"],
            title=pi["title"],
            description=pi["description"],
            total_questions=pi["total_questions"],
            time_limit_minutes=pi["time_limit_minutes"],
            pass_score=pi["pass_score"],
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        print(f"  ✓ 创建试卷: id={paper.id}")
        
        # 创建题目
        for q_data in crawled_data["questions"]:
            question = ExamQuestion(
                paper_id=paper.id,
                question_number=q_data["question_number"],
                question_type=q_data["question_type"],
                stem=q_data["stem"],
                options=q_data["options"],
                answer=q_data["answer"],
                explanation=q_data["explanation"],
                group_id=q_data["group_id"],
                shared_stem=q_data["shared_stem"],
            )
            db.add(question)
        
        db.commit()
        print(f"  ✓ 导入 {len(crawled_data['questions'])} 道题目")
        paper_id = paper.id
        
    except Exception as e:
        db.rollback()
        print(f"  ✗ 导入失败: {e}")
        raise
    finally:
        db.close()
    
    return paper_id


def main():
    print("=" * 60)
    print("hqwx.com 题库爬虫 - 中药一模拟试卷")
    print("=" * 60)
    
    all_data = []
    
    for paper_info in PAPERS:
        crawled = crawl_paper(paper_info)
        if crawled:
            all_data.append(crawled)
            # 保存JSON备份
            json_file = os.path.join(os.path.dirname(__file__), f"tiku_paper_{paper_info['paperId']}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(crawled, f, ensure_ascii=False, indent=2)
            print(f"  ✓ JSON备份: {json_file}")
            
            # 导入数据库
            import_to_db(crawled)
        
        # 间隔一下避免请求太快
        time.sleep(1)
    
    # 汇总
    print(f"\n{'='*60}")
    print(f"爬取完成！共 {len(all_data)} 套试卷")
    for d in all_data:
        pi = d["paper_info"]
        print(f"  - {pi['title']}: {pi['total_questions']}题")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
