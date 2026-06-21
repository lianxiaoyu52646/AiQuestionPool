"""
爬取233网校执业药师中药学历年真题
尝试获取3科×5年=15套真题卷的题目数据
"""
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 233网校中药学三科的真题列表页URL
SUBJECT_URLS = {
    "中药学专业知识一": "https://www.233.com/yaoshi/zhongyao/one/zhenti/",
    "中药学专业知识二": "https://www.233.com/yaoshi/zhongyao/Two/zhenti/",
    "中药学综合知识与技能": "https://www.233.com/yaoshi/zhongyao/zonghe/zhenti/",
}

# 已知的真题详情页URL（从搜索结果中获取）
KNOWN_EXAM_URLS = {
    "中药学专业知识一": {
        2023: "https://www.233.com/yaoshi/zhongyao/one/zhenti/202310/21103221565780.html",
    },
    "中药学专业知识二": {
        2023: "https://www.233.com/yaoshi/zhongyao/Two/zhenti/202310/21170917779016.html",
    },
    "中药学综合知识与技能": {
        2023: "https://www.233.com/yaoshi/zhongyao/zonghe/zhenti/202310/2219111923994.html",
    },
}


def fetch_page(url, retries=3):
    """获取网页内容"""
    for i in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            if resp.status_code == 200:
                return resp.text
            else:
                print(f"  HTTP {resp.status_code} for {url}")
        except Exception as e:
            print(f"  请求失败({i+1}/{retries}): {e}")
            time.sleep(2)
    return None


def parse_exam_page(html, subject, year):
    """
    解析真题详情页，提取题目
    233网校的真题页面格式：
    - 题号. 题干
    A. 选项A
    B. 选项B
    C. 选项C
    D. 选项D
    E. 选项E
    [查看答案](javascript:;)
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # 尝试找到正文内容区域
    content_area = soup.find('div', class_='content') or soup.find('div', class_='article-content') or soup.find('div', class_='detail-content')
    if not content_area:
        # 尝试直接从页面文本提取
        content_area = soup.find('body')
    
    if not content_area:
        print(f"  无法找到内容区域")
        return []
    
    # 获取纯文本
    text = content_area.get_text('\n', strip=True)
    
    # 用正则匹配题目
    # 格式: 数字. 题干内容 A. B. C. D. E.
    questions = []
    
    # 先尝试按题号分割
    # 匹配 "1." "2." 等开头的行
    question_pattern = re.compile(r'^(\d+)[\.．、]\s*(.+?)(?=\d+[\.．、]|\Z)', re.DOTALL | re.MULTILINE)
    
    # 另一种方式：直接从HTML结构提取
    # 233网校的题目通常在<p>标签中
    paragraphs = content_area.find_all(['p', 'div'])
    
    current_question = None
    current_options = {}
    current_stem = ""
    current_answer = None
    
    for p in paragraphs:
        p_text = p.get_text(strip=True)
        if not p_text:
            continue
        
        # 匹配题号开头: "1." "2." 等
        q_match = re.match(r'^(\d+)[\.．、]\s*(.+)', p_text)
        if q_match and not p_text.startswith(('A.', 'B.', 'C.', 'D.', 'E.', 'A．', 'B．', 'C．', 'D．', 'E．')):
            q_num = int(q_match.group(1))
            q_text = q_match.group(2)
            
            # 如果已经有题目在收集，保存它
            if current_question and current_stem:
                questions.append({
                    "question_number": current_question,
                    "stem": current_stem.strip(),
                    "options": current_options.copy(),
                    "answer": current_answer,
                    "subject": subject,
                    "year": year,
                })
            
            # 开始新题目
            current_question = q_num
            current_stem = q_text
            current_options = {}
            current_answer = None
            continue
        
        # 匹配选项
        opt_match = re.match(r'^([ABCDE])[\.．、]\s*(.+)', p_text)
        if opt_match:
            opt_letter = opt_match.group(1)
            opt_text = opt_match.group(2)
            current_options[opt_letter] = opt_text
            continue
        
        # 匹配答案 (有些题目直接在选项后给出答案，如 "9.散剂按医疗用途可分为 (D)")
        ans_match = re.search(r'[\(（]([ABCDE]+)[\)）]', p_text)
        if ans_match and current_question:
            current_answer = ans_match.group(1)
        
        # 追加到题干
        if current_question and not opt_match and not q_match:
            current_stem += " " + p_text
    
    # 保存最后一题
    if current_question and current_stem:
        questions.append({
            "question_number": current_question,
            "stem": current_stem.strip(),
            "options": current_options.copy(),
            "answer": current_answer,
            "subject": subject,
            "year": year,
        })
    
    return questions


def find_exam_links(list_url, subject):
    """从真题列表页找到各年份的真题链接"""
    html = fetch_page(list_url)
    if not html:
        print(f"  无法获取列表页: {list_url}")
        return {}
    
    soup = BeautifulSoup(html, 'html.parser')
    links = {}
    
    # 查找所有链接
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True)
        href = a['href']
        
        # 匹配年份
        for year in range(2019, 2025):
            if str(year) in text and '真题' in text and subject in text:
                if not href.startswith('http'):
                    href = 'https://www.233.com' + href
                links[year] = href
                break
    
    return links


def crawl_all_exams():
    """爬取所有真题"""
    all_exams = {}
    
    for subject, list_url in SUBJECT_URLS.items():
        print(f"\n{'='*60}")
        print(f"正在处理: {subject}")
        print(f"{'='*60}")
        
        # 先从已知URL开始
        exam_urls = KNOWN_EXAM_URLS.get(subject, {}).copy()
        
        # 尝试从列表页找更多年份的链接
        print(f"  搜索列表页: {list_url}")
        found_links = find_exam_links(list_url, subject)
        exam_urls.update(found_links)
        
        print(f"  找到 {len(exam_urls)} 个年份的真题URL: {list(exam_urls.keys())}")
        
        all_exams[subject] = {}
        
        for year, url in sorted(exam_urls.items()):
            print(f"\n  爬取 {year} 年真题: {url}")
            html = fetch_page(url)
            if not html:
                print(f"  获取失败，跳过")
                continue
            
            questions = parse_exam_page(html, subject, year)
            print(f"  解析到 {len(questions)} 道题")
            
            if questions:
                all_exams[subject][year] = {
                    "url": url,
                    "question_count": len(questions),
                    "questions": questions,
                }
            
            time.sleep(1)  # 礼貌等待
    
    return all_exams


def main():
    print("=" * 60)
    print("执业药师中药学历年真题爬虫")
    print("=" * 60)
    
    results = crawl_all_exams()
    
    # 统计
    print("\n" + "=" * 60)
    print("爬取结果统计:")
    print("=" * 60)
    total = 0
    for subject, years in results.items():
        print(f"\n{subject}:")
        for year, data in sorted(years.items()):
            print(f"  {year}年: {data['question_count']}题")
            total += data['question_count']
    print(f"\n总计: {total} 题")
    
    # 保存结果
    output_path = os.path.join(os.path.dirname(__file__), "crawled_exams.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_path}")
    
    return results


if __name__ == "__main__":
    main()
