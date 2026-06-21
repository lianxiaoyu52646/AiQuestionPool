# -*- coding: utf-8 -*-
"""
环球网校(hqwx.com)真题爬虫 — 抓取2024/2025年中药学执业药师真题

策略：
1. 从环球网校真题页面抓取HTML内容
2. 用正则解析题目结构（题号、题干、选项、答案、解析）
3. 直接写入exam_papers / exam_questions表
4. 支持断点续传（已存在的题目会被更新）

用法：
  python crawl_hqwx.py                    # 抓取所有(2024+2025)
  python crawl_hqwx.py --year 2025        # 仅抓取2025年
  python crawl_hqwx.py --year 2024        # 仅抓取2024年
  python crawl_hqwx.py --subject "中药学专业知识一"  # 仅抓取指定科目
  python crawl_hqwx.py --list             # 查看已抓取进度
"""
import sys
import os
import re
import json
import time
import argparse
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.exam_models import ExamPaper, ExamQuestion

# ============================================================
# 环球网校真题页面配置
# ============================================================

# 每个科目+年份对应一个"完整版"页面URL
# 这些页面包含最佳选择题(40题)的部分内容，其余题型需从分题型页面补充
HQWX_PAGES = {
    2025: {
        "中药学专业知识一": {
            "complete": "https://www.hqwx.com/zyys-kaoshi/news/17609232576359.html",
            "duoxiang": "https://www.hqwx.com/zyys-kaoshi/news/17610261353504.html",
            "zonghe": "https://www.hqwx.com/zyys-kaoshi/news/17610259927503.html",
        },
        "中药学专业知识二": {
            "complete": "https://www.hqwx.com/zyys-kaoshi/news/17609236437496.html",
            "zuijia": "https://www.hqwx.com/zyys-kaoshi/news/17610935076528.html",
            "peiwu": "https://www.hqwx.com/zyys-kaoshi/news/17610937093331.html",
            "zonghe": "https://www.hqwx.com/zyys-kaoshi/news/17610938697723.html",
            "duoxiang": "https://www.hqwx.com/zyys-kaoshi/news/17610940011071.html",
        },
        "中药学综合知识与技能": {
            "complete": "https://www.hqwx.com/zyys-kaoshi/news/17609244618760.html",
            "zuijia": "https://www.hqwx.com/zyys-kaoshi/news/17610951713477.html",
            "peiwu": "https://www.hqwx.com/zyys-kaoshi/news/17610953359277.html",
            "zonghe": "https://www.hqwx.com/zyys-kaoshi/news/17610955938917.html",
            "duoxiang": "https://www.hqwx.com/zyys-kaoshi/news/17610957693735.html",
        },
    },
    # 2024年真题页面内容质量差：3个科目使用相同的通用页面，题目跨科目且不完整
    # 暂不抓取2024年数据，待找到更好的数据源后再补充
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_page(url, retries=3):
    """获取网页内容"""
    for i in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            if resp.status_code == 200:
                return resp.text
            else:
                print(f"  ⚠️ HTTP {resp.status_code}, 重试 {i+1}/{retries}")
        except Exception as e:
            print(f"  ⚠️ 请求失败: {e}, 重试 {i+1}/{retries}")
        time.sleep(2)
    return None


def extract_article_content(html):
    """从HTML中提取文章正文文本"""
    # 移除script和style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # 尝试提取文章主体 — hqwx.com使用 <section class="news_content"> 或类似容器
    # 尝试多种选择器
    content_patterns = [
        r'<section[^>]*class="[^"]*news_content[^"]*"[^>]*>(.*?)</section>',
        r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*footer|<div[^>]*class="[^"]*share)',
        r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*footer|<div[^>]*class="[^"]*share)',
        r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*footer|<div[^>]*class="[^"]*share)',
    ]
    
    for pattern in content_patterns:
        article_match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if article_match:
            html = article_match.group(1)
            break
    
    # 将HTML标签转为换行
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<div[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h[1-6][^>]*>', '\n', text, flags=re.IGNORECASE)
    
    # 移除所有剩余HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 解码HTML实体
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&ldquo;', '"').replace('&rdquo;', '"')
    
    # 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


def parse_questions_from_text(text, subject, year):
    """
    从纯文本中解析题目 — 逐行解析，支持多种格式
    
    支持的格式:
    1. A型题(最佳选择): 数字.题干 → A.B.C.D.E.选项 → 【答案】X → 【解析】
    2. B型题(配伍): 考点XX【X-Y】→ A.B.C.D.E.选项 → 数字.题干 → 数字.【答案】X → 【解析】
       注意: B型题中后续题目的题干可能没有题号前缀
    3. C型题(综合分析): 【X-Y】共享题干 → 数字.题干 → A.B.C.D.E.选项 → 【答案】X → 【解析】
    4. X型题(多项选择): 同A型但答案为多字母
    """
    questions = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # ========== 第1步: 识别配伍/综合题分组 ==========
    # 格式: "考点41【41-42】" 或 "【41-42】" 或 "[41-42]"
    # 后面可能跟共享选项(B型)或共享题干(C型)
    b_type_groups = {}  # {题号: {options, shared_stem, group_id, group_range: (start, end)}}
    group_ranges = []  # [(start_num, end_num, line_index_of_group_marker)]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        # 匹配分组标记
        group_match = re.search(r'(?:考点\d+)?\s*[【\[](\d+)-(\d+)[】\]]', line)
        if group_match:
            start_num = int(group_match.group(1))
            end_num = int(group_match.group(2))
            if end_num - start_num <= 10 and end_num > start_num:
                # 提取分组标记后的共享内容（可能是选项或题干）
                options = {}
                
                # 向后搜索选项
                j = i + 1
                while j < len(lines) and j < i + 10:
                    opt_match = re.match(r'^([A-E])\.\s*(.+)', lines[j])
                    if opt_match:
                        options[opt_match.group(1)] = clean_text(opt_match.group(2))
                        j += 1
                        continue
                    # E选项可能没有前缀（hqwx.com页面E选项常省略"E."前缀）
                    if len(options) == 4 and 'E' not in options:
                        if (not re.match(r'^\d+\.', lines[j]) 
                            and not lines[j].startswith('【') 
                            and not re.match(r'^[A-E]\.', lines[j])
                            and not lines[j].startswith('考点')
                            and len(lines[j]) >= 2):
                            options['E'] = clean_text(lines[j])
                            j += 1
                            continue
                    break
                
                # 判断是B型(有选项)还是C型(有共享题干文字)
                has_options = len(options) >= 2
                shared_stem = f'[{start_num}-{end_num}]'
                
                # 如果分组标记行有额外文字（如案例描述），保存为shared_stem
                extra_text = line[group_match.end():].strip()
                if extra_text and len(extra_text) > 10:
                    shared_stem = f'[{start_num}-{end_num}] {extra_text}'
                
                for n in range(start_num, end_num + 1):
                    b_type_groups[n] = {
                        'options': options if has_options else {},
                        'shared_stem': shared_stem,
                        'has_options': has_options,
                        'group_range': (start_num, end_num),
                    }
                group_ranges.append((start_num, end_num, i, has_options))
        i += 1
    
    # ========== 第1.5步: 预处理 — 为B型题中无题号的题干添加题号 ==========
    # B型题格式: 考点XX【X-Y】→ 选项 → X.题干1 → 题干2(无题号) → 题干3(无题号) → X.【答案】 → Y.【答案】
    # 策略: 在每个B型组中，找到第一个有题号的题干，然后为后续无题号的行添加题号
    new_lines = lines[:]
    for start_num, end_num, group_line_idx, has_options in group_ranges:
        if not has_options:
            continue  # C型题不需要预处理
        
        # 在group_line_idx之后，选项之后，找到题干区域
        # 题干区域: 从第一个有题号的行开始，到第一个【答案】行结束
        stem_start_idx = None
        stem_end_idx = None
        expected_q_num = start_num
        
        for j in range(group_line_idx + 1, len(new_lines)):
            line = new_lines[j]
            # 遇到答案行，题干区域结束
            if re.match(r'^(?:(\d+)\.)?\s*【答案】', line):
                stem_end_idx = j
                break
            # 遇到下一个考点/分组标记，题干区域结束
            if j > group_line_idx + 1 and re.search(r'(?:考点\d+)?\s*[【\[]\d+-\d+[】\]]', line):
                stem_end_idx = j
                break
            # 找到第一个有题号的题干
            if stem_start_idx is None:
                q_match = re.match(r'^(\d+)\.\s*(.+)', line)
                if q_match and int(q_match.group(1)) == start_num:
                    stem_start_idx = j
                    expected_q_num = start_num + 1
            else:
                # 在题干区域中，检查有题号的行
                q_match = re.match(r'^(\d+)\.\s*(.+)', line)
                if q_match:
                    expected_q_num = int(q_match.group(1)) + 1
                else:
                    # 无题号的行 — 如果不是选项行，则是下一题的题干
                    if not re.match(r'^[A-E]\.', line) and not line.startswith('考点') and not line.startswith('【'):
                        # 为这行添加题号前缀
                        new_lines[j] = f"{expected_q_num}.{line}"
                        expected_q_num += 1
    
    lines = new_lines
    
    # ========== 第2步: 逐行解析题目 ==========
    # B型题格式特殊: 题干在答案之前 (42.题干 → 41.【答案】C → 42.【答案】D)
    # 所以我们先收集所有题干和答案，然后再匹配
    
    # 收集题干: {题号: [题干行]}
    stems_by_num = {}
    # 收集答案: {题号: 答案}
    answers_by_num = {}
    # 收集解析: {题号: [解析行]}
    explanations_by_num = {}
    # 收集选项: {题号: {A:text, ...}}
    options_by_num = {}
    
    current_q_num = None
    current_stem = []
    current_options = {}
    current_answer = None
    current_explanation = []
    in_explanation = False
    
    def save_collected():
        """Save current question data to stems_by_num etc."""
        nonlocal current_q_num, current_stem, current_options, current_answer, current_explanation
        if current_q_num is not None:
            # Only save stem if not already saved (avoid contamination from next group's options)
            if current_stem and current_q_num not in stems_by_num:
                stems_by_num[current_q_num] = list(current_stem)
            if current_options:
                options_by_num.setdefault(current_q_num, {}).update(current_options)
            if current_answer:
                answers_by_num[current_q_num] = current_answer
            if current_explanation:
                explanations_by_num.setdefault(current_q_num, []).extend(current_explanation)
        
        current_stem = []
        current_options = {}
        current_answer = None
        current_explanation = []
    
    for line in lines:
        # 检查是否是答案行: "【答案】X" 或 "数字.【答案】X"
        ans_match = re.match(r'^(?:(\d+)\.)?\s*【答案】\s*([A-E]+(?:[、,][A-E]+)*)', line)
        if ans_match:
            if ans_match.group(1):
                q_num = int(ans_match.group(1))
                if current_q_num is not None and current_q_num != q_num:
                    save_collected()
                current_q_num = q_num
            current_answer = ans_match.group(2)
            in_explanation = False
            continue
        
        # 检查是否是解析行: "【解析】text"
        expl_match = re.match(r'^【解析】\s*(.*)', line)
        if expl_match:
            in_explanation = True
            if expl_match.group(1):
                current_explanation.append(expl_match.group(1))
            continue
        
        if in_explanation:
            if re.match(r'^\d+\.', line) or line.startswith('【答案】') or line.startswith('考点') or line.startswith('【') or line.startswith('由于篇幅') or line.startswith('以上就是'):
                in_explanation = False
            else:
                current_explanation.append(line)
                continue
        
        # 检查是否是选项行: "A.text" "B.text" etc.
        opt_match = re.match(r'^([A-E])\.\s*(.+)', line)
        if opt_match:
            current_options[opt_match.group(1)] = clean_text(opt_match.group(2))
            continue
        
        # 检查是否是题目行: "数字.text"
        q_match = re.match(r'^(\d+)\.\s*(.+)', line)
        if q_match:
            q_num = int(q_match.group(1))
            if current_q_num is not None and current_q_num != q_num:
                save_collected()
            current_q_num = q_num
            current_stem.append(q_match.group(2))
            in_explanation = False
            continue
        
        # 检查是否是分组标记行
        if re.search(r'[【\[]\d+-\d+[】\]]', line):
            # 遇到新分组标记时，先保存当前题目，防止下一组选项污染
            if current_q_num is not None:
                save_collected()
            if re.match(r'^(?:考点\d+)?\s*[【\[]\d+-\d+[】\]]\s*$', line):
                continue
            continue
        
        # E选项检测：已收集A-D且当前行是纯文本（非题号、非答案、非分组标记）
        if len(current_options) == 4 and 'E' not in current_options:
            if (not re.match(r'^\d+\.', line) 
                and not line.startswith('【') 
                and not re.match(r'^[A-E]\.', line)
                and not line.startswith('考点')
                and not line.startswith('执业药师')
                and not line.startswith('由于篇幅')
                and not line.startswith('以上就是')
                and len(line) > 1):
                current_options['E'] = clean_text(line)
                continue
        
        # 其他文本：可能是题干的延续
        if current_q_num is not None and not in_explanation:
            if not line.startswith('考点') and not line.startswith('执业药师') and not line.startswith('合格标准') and not line.startswith('由于篇幅') and not line.startswith('以上就是') and not line.startswith('完整版') and not line.startswith('预计') and not line.startswith('点击') and not line.startswith('分享到') and not line.startswith('编辑'):
                current_stem.append(line)
    
    # 保存最后一个题目
    save_collected()
    
    # ========== 第3步: 合并题干和答案 ==========
    all_q_nums = set(stems_by_num.keys()) | set(answers_by_num.keys())
    
    for q_num in all_q_nums:
        stem = clean_text(' '.join(stems_by_num.get(q_num, [])))
        answer = answers_by_num.get(q_num, '')
        if answer:
            answer = answer.replace('、', '').replace(',', '').replace(' ', '')
        explanation = clean_text(' '.join(explanations_by_num.get(q_num, [])))
        options = options_by_num.get(q_num, {})
        
        # 判断题型
        if q_num in b_type_groups:
            group_info = b_type_groups[q_num]
            # B型题：始终使用分组选项（Step 1中已正确解析含E选项）
            # 避免Step 2中选项错位污染
            if group_info['has_options']:
                # 合并：优先使用分组选项，Step 2收集的作为补充
                if group_info['options']:
                    options = group_info['options']
            if group_info['has_options']:
                q_type = 'B'
            else:
                q_type = 'C'
            shared_stem = group_info['shared_stem']
        elif len(answer) > 1:
            q_type = 'X'
            shared_stem = None
        else:
            q_type = 'A'
            shared_stem = None
        
        # 只保存有答案的题目
        if answer:
            questions.append({
                'question_number': q_num,
                'question_type': q_type,
                'stem': stem,
                'options': options,
                'answer': answer,
                'explanation': explanation,
                'shared_stem': shared_stem,
            })
    
    # 去重
    seen = set()
    unique_questions = []
    for q in questions:
        if q['question_number'] not in seen:
            seen.add(q['question_number'])
            unique_questions.append(q)
    
    unique_questions.sort(key=lambda x: x['question_number'])
    
    return unique_questions


def parse_options(options_text):
    """解析选项文本，返回 {A: text, B: text, ...}"""
    options = {}
    # 匹配 A.选项内容 B.选项内容 ...
    opt_pattern = re.compile(r'([A-E])\.\s*(.+?)(?=\n[A-E]\.|\Z)', re.DOTALL)
    for match in opt_pattern.finditer(options_text):
        letter = match.group(1)
        text = clean_text(match.group(2).strip())
        options[letter] = text
    return options


def clean_text(text):
    """清理文本中的多余空白和HTML残留"""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    # 移除()内的空行
    text = re.sub(r'\(\s*\)', '()', text)
    return text


def get_or_create_paper(db, subject, year, title):
    """获取或创建试卷记录"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.subject == subject,
        ExamPaper.year == year
    ).first()
    if not paper:
        paper = ExamPaper(
            subject=subject,
            year=year,
            title=title,
            description=f"{year}年执业药师{subject}真题（环球网校考生回忆版）",
            total_questions=120,
            time_limit_minutes=120,
            pass_score=72
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        print(f"  ✅ 创建试卷: {title} (id={paper.id})")
    return paper


def save_questions_batch(db, paper_id, questions_data):
    """批量保存题目到数据库"""
    if not questions_data:
        return 0
    
    saved = 0
    for q_data in questions_data:
        existing = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == paper_id,
            ExamQuestion.question_number == q_data['question_number']
        ).first()
        
        if existing:
            existing.question_type = q_data['question_type']
            existing.stem = q_data['stem']
            existing.options = q_data['options']
            existing.answer = q_data['answer']
            existing.explanation = q_data['explanation']
            if q_data.get('shared_stem'):
                existing.shared_stem = q_data['shared_stem']
        else:
            q = ExamQuestion(
                paper_id=paper_id,
                question_number=q_data['question_number'],
                question_type=q_data['question_type'],
                stem=q_data['stem'],
                options=q_data['options'],
                answer=q_data['answer'],
                explanation=q_data['explanation'],
                shared_stem=q_data.get('shared_stem'),
                group_id=q_data.get('group_id'),
            )
            db.add(q)
        saved += 1
    
    db.commit()
    return saved


def crawl_subject_year(db, subject, year):
    """抓取指定科目和年份的真题"""
    print(f"\n{'='*60}")
    print(f"📋 抓取: {year}年 {subject}")
    print(f"{'='*60}")
    
    if year not in HQWX_PAGES or subject not in HQWX_PAGES[year]:
        print(f"  ❌ 未找到 {year}年 {subject} 的页面配置")
        return 0
    
    page_config = HQWX_PAGES[year][subject]
    
    # 创建试卷
    title = f"{year}年执业药师考试《{subject}》真题及解析"
    paper = get_or_create_paper(db, subject, year, title)
    
    # 检查已有题目数
    existing_count = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper.id
    ).count()
    if existing_count > 0:
        print(f"  ℹ️ 已有 {existing_count} 题，将更新/补充")
    
    all_questions = {}
    
    # 抓取完整版页面
    for page_type, url in page_config.items():
        print(f"\n  📄 抓取页面 [{page_type}]: {url}")
        html = fetch_page(url)
        if not html:
            print(f"  ❌ 页面获取失败")
            continue
        
        text = extract_article_content(html)
        
        # 定位真题内容区域
        # 注意：标记必须足够具体，避免匹配到标题中的"综合知识与技能"等
        start_markers = [
            '一、最佳选择题', '一、 最佳选择题', '最佳选择题(40题)', '最佳选择题(45题)', '一、最佳选择',
            '二、配伍选择题', '二、 配伍选择题', '执业药师配伍选择题', '配伍选择题(45题)', '配伍选择题',
            '三、综合选择题', '三、 综合选择题', '综合选择题(10题)', '执业药师综合分析题', '综合分析题(10题)', '综合分析题', '执业药师综合选择题',
            '四、多项选择题', '四、 多项选择题', '执业药师多项选择题', '多项选择题(5题)', '多项选择题(10题)', '多项选择',
            '考点',  # 配伍题页面用"考点XX"标记
        ]
        # end_markers只用于截断尾部无关内容，不会截断题目内容
        # 注意："由于篇幅有限"可能出现在文章开头的引言中，需要特殊处理
        end_markers = ['以上就是小编', '执业药师考试成绩', '合格标准']
        
        start_pos = -1
        for marker in start_markers:
            pos = text.find(marker)
            if pos != -1:
                start_pos = pos
                break
        
        if start_pos == -1:
            # 尝试直接从第一个题号开始
            q_match = re.search(r'(?:^|\n)\d+\.\s', text)
            if q_match:
                start_pos = q_match.start()
        
        if start_pos == -1:
            # 尝试找【答案】标记
            ans_match = text.find('【答案】')
            if ans_match != -1:
                # 向前找一些内容
                start_pos = max(0, ans_match - 500)
            else:
                print(f"  ⚠️ 未找到题目起始位置，跳过")
                continue
        
        # 验证start_pos是否在合理位置：如果start_pos在【答案】之后，说明匹配到了文末导航
        ans_pos = text.find('【答案】', start_pos)
        if ans_pos == -1 or ans_pos - start_pos > 5000:
            # start_pos可能匹配到了文末的导航链接，尝试用题号定位
            q_match = re.search(r'(?:^|\n)\d+\.\s', text)
            if q_match and q_match.start() < start_pos:
                start_pos = q_match.start()
            else:
                # 用【答案】位置向前找
                ans_pos2 = text.find('【答案】')
                if ans_pos2 != -1:
                    start_pos = max(0, ans_pos2 - 500)
        
        # 确保end_pos在start_pos之后，且至少有一些内容
        end_pos = len(text)
        for marker in end_markers:
            pos = text.find(marker, start_pos + 50)  # 至少跳过50字符避免匹配到标题
            if pos != -1 and pos < end_pos:
                end_pos = pos
        
        content = text[start_pos:end_pos]
        print(f"  📝 提取到 {len(content)} 字符的题目内容")
        
        # 解析题目
        questions = parse_questions_from_text(content, subject, year)
        print(f"  🔍 解析出 {len(questions)} 道题目")
        
        for q in questions:
            all_questions[q['question_number']] = q
    
    if not all_questions:
        print(f"  ❌ 未解析到任何题目")
        return 0
    
    # 转为列表并排序
    questions_list = sorted(all_questions.values(), key=lambda x: x['question_number'])
    
    # 为B型题分配group_id
    group_counter = 0
    prev_shared = None
    for q in questions_list:
        if q.get('shared_stem') and q['shared_stem'] != prev_shared:
            group_counter += 1
            prev_shared = q['shared_stem']
        if q.get('shared_stem'):
            q['group_id'] = f"{year}_{subject[:2]}_G{group_counter}"
        else:
            q['group_id'] = None
    
    # 保存到数据库
    saved = save_questions_batch(db, paper.id, questions_list)
    print(f"\n  ✅ 共保存/更新 {saved} 道题目 (试卷ID={paper.id})")
    
    # 统计题型分布
    type_counts = {}
    for q in questions_list:
        t = q['question_type']
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"  📊 题型分布: {type_counts}")
    
    # 检查数据质量
    no_answer = sum(1 for q in questions_list if not q['answer'])
    no_explanation = sum(1 for q in questions_list if not q['explanation'])
    no_options = sum(1 for q in questions_list if not q['options'])
    print(f"  ⚠️ 无答案: {no_answer}, 无解析: {no_explanation}, 无选项: {no_options}")
    
    return saved


def show_progress(db):
    """显示已抓取的试卷进度"""
    papers = db.query(ExamPaper).order_by(ExamPaper.year, ExamPaper.subject).all()
    print(f"\n{'='*60}")
    print(f"📊 试卷进度")
    print(f"{'='*60}")
    print(f"{'ID':<5} {'年份':<6} {'科目':<25} {'题数':<6} {'标题'}")
    print(f"{'-'*80}")
    for p in papers:
        q_count = db.query(ExamQuestion).filter(ExamQuestion.paper_id == p.id).count()
        print(f"{p.id:<5} {p.year:<6} {p.subject:<25} {q_count:<6} {p.title[:40]}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description='环球网校真题爬虫')
    parser.add_argument('--year', type=int, help='年份: 2024 或 2025')
    parser.add_argument('--subject', type=str, help='科目名称')
    parser.add_argument('--list', action='store_true', help='查看已抓取进度')
    args = parser.parse_args()
    
    db = SessionLocal()
    
    try:
        if args.list:
            show_progress(db)
            return
        
        years = [args.year] if args.year else [2025, 2024]
        subjects = [args.subject] if args.subject else list(HQWX_PAGES.get(years[0], {}).keys())
        
        total_saved = 0
        for year in years:
            year_subjects = [args.subject] if args.subject else list(HQWX_PAGES.get(year, {}).keys())
            for subject in year_subjects:
                saved = crawl_subject_year(db, subject, year)
                total_saved += saved
        
        print(f"\n{'='*60}")
        print(f"🎉 全部完成！共保存/更新 {total_saved} 道题目")
        print(f"{'='*60}")
        
        show_progress(db)
        
    finally:
        db.close()


if __name__ == '__main__':
    main()
