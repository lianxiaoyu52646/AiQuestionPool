# -*- coding: utf-8 -*-
"""
233网校真题爬虫 - 多智能体协同版

策略：
1. 多个Agent Worker并行爬取不同科目/年份的试卷
2. 每个Worker使用独立的浏览器Tab，共享同一个浏览器实例
3. 模拟真人操作：随机等待、鼠标轨迹、阅读停留
4. 断点续传：每题立即commit，中断后可继续
5. 上下文管理：token超阈值时自动压缩旧消息（仿Claude Code）

用法：
  python crawl_233_multiagent.py --list              # 查看所有试卷进度
  python crawl_233_multiagent.py --create            # 仅创建试卷记录
  python crawl_233_multiagent.py --workers 3         # 3个Worker并行爬取
  python crawl_233_multiagent.py --subject "中药学专业知识一"  # 爬取指定科目
  python crawl_233_multiagent.py --paper-id 2        # 爬取指定试卷
"""
import sys
import os
import time
import random
import json
import argparse
import re
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.exam_models import ExamPaper, ExamQuestion

# ============================================================
# 233网校真题页面配置
# subjectId: 308=中药学专一, 309=中药学专二, 311=中药学综合
# 真题列表URL: https://ks.233.com/{subjectId}/2
# 做题页面URL: https://wx.233.com/center/extract-question/exercise/{paperCode}?type=2&attachType=5
# ============================================================

# 试卷直接链接映射 (从233网校真题列表页获取)
# 格式: (subject_id, year) -> exam_item_id
PAPER_DIRECT_LINKS = {
    (311, 2023): 430033,  # 综合2023
    (311, 2022): 421966,  # 综合2022
    (311, 2021): 411721,  # 综合2021
    (311, 2020): 400225,  # 综合2020
    (308, 2023): 429878,  # 专一2023
    (308, 2022): 421947,  # 专一2022
    (308, 2021): 411719,  # 专一2021
    (308, 2020): 400238,  # 专一2020
    (309, 2023): 429879,  # 专二2023
    (309, 2022): 421964,  # 专二2022
    (309, 2021): 411713,  # 专二2021
    (309, 2020): 400234,  # 专二2020
}

EXAM_CONFIGS = [
    {
        "subject": "中药学综合知识与技能",
        "subject_id": 311,
        "papers": [
            {"year": 2023, "title": "2023年执业药师考试《中药学综合知识与技能》真题及解析"},
            {"year": 2022, "title": "2022年执业药师考试《中药学综合知识与技能》真题及解析"},
            {"year": 2021, "title": "2021年执业药师考试《中药学综合知识与技能》真题及解析"},
            {"year": 2020, "title": "2020年执业药师考试《中药学综合知识与技能》真题及解析"},
        ]
    },
    {
        "subject": "中药学专业知识一",
        "subject_id": 308,
        "papers": [
            {"year": 2023, "title": "2023年执业药师考试《中药学专业知识一》真题及解析"},
            {"year": 2022, "title": "2022年执业药师考试《中药学专业知识（一）》真题及解析"},
            {"year": 2021, "title": "2021年执业药师考试《中药学专业知识（一）》真题及解析"},
            {"year": 2020, "title": "2020年执业药师考试《中药学专业知识（一）》真题及解析"},
        ]
    },
    {
        "subject": "中药学专业知识二",
        "subject_id": 309,
        "papers": [
            {"year": 2023, "title": "2023年执业药师考试《中药学专业知识二》真题及解析"},
            {"year": 2022, "title": "2022年执业药师考试《中药学专业知识（二）》真题及解析"},
            {"year": 2021, "title": "2021年执业药师考试《中药学专业知识（二）》真题及解析"},
            {"year": 2020, "title": "2020年执业药师考试《中药学专业知识（二）》真题及解析"},
        ]
    },
]


# ============================================================
# 数据库操作
# ============================================================

def get_or_create_paper(db, subject, year, title, url=""):
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
            description=f"{year}年执业药师{subject}真题",
            total_questions=120,
            time_limit_minutes=120,
            pass_score=72
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        print(f"  ✅ 创建试卷: {title} (id={paper.id})")
    return paper


def get_crawled_count(db, paper_id):
    return db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper_id
    ).count()


def get_crawled_question_numbers(db, paper_id):
    rows = db.query(ExamQuestion.question_number).filter(
        ExamQuestion.paper_id == paper_id
    ).all()
    return set(r[0] for r in rows)


def save_question(db, paper_id, question_number, question_type, stem,
                  options, answer, explanation, group_id=None, shared_stem=None):
    """保存单题到数据库（立即commit）"""
    existing = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper_id,
        ExamQuestion.question_number == question_number
    ).first()
    if existing:
        existing.question_type = question_type
        existing.stem = stem
        existing.options = options
        existing.answer = answer
        existing.explanation = explanation
        if group_id:
            existing.group_id = group_id
        if shared_stem:
            existing.shared_stem = shared_stem
    else:
        q = ExamQuestion(
            paper_id=paper_id,
            question_number=question_number,
            question_type=question_type,
            stem=stem,
            options=options,
            answer=answer,
            explanation=explanation,
            group_id=group_id,
            shared_stem=shared_stem
        )
        db.add(q)
    db.commit()


def save_questions_batch(db, paper_id, questions_data):
    """批量保存题目到数据库（一次commit）
    
    Args:
        db: 数据库session
        paper_id: 试卷ID
        questions_data: list of dict, 每个dict包含:
            question_number, question_type, stem, options, answer, explanation, shared_stem
    
    Returns:
        saved_count: 实际保存/更新的数量
    """
    if not questions_data:
        return 0
    
    # 为B/C型题分配group_id（从shared_stem中的"回答41-42题"提取题号范围）
    import re as _re
    group_counter = 0
    current_group_id = None
    current_group_range = None  # (start, end)
    
    for q_data in questions_data:
        q_num = q_data['question_number']
        q_type = q_data.get('question_type', 'A')
        shared_stem = q_data.get('shared_stem', '')
        
        # B/C型题：从shared_stem中提取题号范围来分配group_id
        if q_type in ('B', 'C') and shared_stem:
            range_match = _re.search(r'回答(\d+)-(\d+)题', shared_stem)
            if range_match:
                start_num, end_num = int(range_match.group(1)), int(range_match.group(2))
                # 如果题号在范围内，使用当前group
                if start_num <= q_num <= end_num:
                    if current_group_range != (start_num, end_num):
                        group_counter += 1
                        current_group_id = f"{q_type}{group_counter}"
                        current_group_range = (start_num, end_num)
                    q_data['group_id'] = current_group_id
                else:
                    q_data['group_id'] = None
            else:
                # 没有范围信息，每道B/C题独立一组
                q_data['group_id'] = None
        else:
            q_data['group_id'] = q_data.get('group_id')
    
    saved_count = 0
    for q_data in questions_data:
        q_num = q_data['question_number']
        existing = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == paper_id,
            ExamQuestion.question_number == q_num
        ).first()
        
        if existing:
            existing.question_type = q_data.get('question_type', 'A')
            existing.stem = q_data['stem']
            existing.options = q_data.get('options', {})
            existing.answer = q_data['answer']
            existing.explanation = q_data.get('explanation', '')
            if q_data.get('shared_stem'):
                existing.shared_stem = q_data['shared_stem']
            if q_data.get('group_id'):
                existing.group_id = q_data['group_id']
        else:
            q = ExamQuestion(
                paper_id=paper_id,
                question_number=q_num,
                question_type=q_data.get('question_type', 'A'),
                stem=q_data['stem'],
                options=q_data.get('options', {}),
                answer=q_data['answer'],
                explanation=q_data.get('explanation', ''),
                shared_stem=q_data.get('shared_stem'),
                group_id=q_data.get('group_id')
            )
            db.add(q)
        saved_count += 1
    
    db.commit()
    return saved_count


def list_papers(db):
    papers = db.query(ExamPaper).order_by(ExamPaper.subject, ExamPaper.year).all()
    if not papers:
        print("数据库中暂无试卷记录")
        return
    print("\n📋 试卷列表:")
    print(f"{'ID':<5} {'科目':<25} {'年份':<6} {'已爬/总数':<12} {'标题'}")
    print("-" * 80)
    for p in papers:
        crawled = get_crawled_count(db, p.id)
        status = "✅完成" if crawled >= p.total_questions else f"⏳{crawled}/{p.total_questions}"
        print(f"{p.id:<5} {p.subject:<25} {p.year:<6} {status:<12} {p.title}")


def create_all_papers(db):
    """创建所有配置中的试卷记录"""
    created = 0
    for config in EXAM_CONFIGS:
        for p_config in config['papers']:
            paper = get_or_create_paper(
                db, config['subject'], p_config['year'], p_config['title']
            )
            created += 1
    print(f"\n✅ 共 {created} 套试卷记录已就绪")
    list_papers(db)


# ============================================================
# 页面数据提取（适配233网校真实页面结构）
# ============================================================

def extract_question_from_page(page):
    """从当前页面提取一道题目的完整数据
    
    233网校练习模式页面结构：
    - 题目容器: .question-view-normal 或 .question-normal（切换题目后class可能变化）
    - 题干区域: .question-view-single 或 .question-single (含题号、题型标签、题干文本)
    - 选项列表: ul.question-options 或 ul.options > li.option
      - A型/X型题: li.option 内含 "A. 选项文本"
      - B型题: li.option 内只有字母 "A"（无文本），实际选项在 .material-content 中
    - 材料区域: .material-content（B型题的共享选项/材料，需先点击 .material-btn 展开）
    - 答案区域: .question-common-result (含"正确答案：B" 或 "正确答案：A,B,C,E")
    - 解析区域: .question-common-explain (含"参考解析："后内容)
    - 底部按钮: .examZt-ltB-next (下一题), .examZt-ltB-ckda (查看答案)
    """
    data = page.evaluate("""
    () => {
      const result = {};
      
      // 题目容器 - 233网校使用 .question-view-normal 或 .question-normal
      const questionDiv = document.querySelector('.question-view-normal') || document.querySelector('.question-normal');
      if (!questionDiv) return {error: 'no question div'};
      
      // 题干区域 - 支持所有题型类名
      // .question-view-single / .question-single = 最佳选择题(A型) 或 配伍选择题(B型，实际也用single)
      // .question-view-multi / .question-multi = 多项选择题(X型)
      // .question-view-batch / .question-batch = 配伍选择题(B型，部分页面可能用)
      // .question-view-comprehensive / .question-comprehensive = 综合分析选择题(C型)
      const titleEl = questionDiv.querySelector(
        '.question-view-single, .question-single, ' +
        '.question-view-multi, .question-multi, ' +
        '.question-view-batch, .question-batch, ' +
        '.question-view-comprehensive, .question-comprehensive'
      );
      const titleText = titleEl ? titleEl.textContent.trim() : questionDiv.textContent.trim();
      
      // 提取题号
      const numMatch = titleText.match(/^(\\d+)\\./);
      result.question_number = numMatch ? parseInt(numMatch[1]) : 0;
      
      // 提取题型
      const typeMatch = titleText.match(/【(.+?)】/);
      let qType = 'A';
      if (typeMatch) {
        const typeName = typeMatch[1];
        if (typeName.includes('最佳选择')) qType = 'A';
        else if (typeName.includes('配伍')) qType = 'B';
        else if (typeName.includes('综合分析')) qType = 'C';
        else if (typeName.includes('多项选择') || typeName.includes('多选')) qType = 'X';
      }
      result.question_type = qType;
      result.type_name = typeMatch ? typeMatch[1] : '';
      
      // 提取题干文本
      // .question-single > div 内有3个span: [题号题型] [题干] [标签]
      if (titleEl) {
        const divEl = titleEl.querySelector('div');
        if (divEl) {
          const spans = divEl.querySelectorAll(':scope > span');
          if (spans.length >= 2) {
            // 第二个span是题干
            result.stem = spans[1].textContent.trim();
          } else {
            // 备用：克隆后移除选项和标签
            const clone = divEl.cloneNode(true);
            clone.querySelectorAll('ul.options, ul.question-options, .question-title-tag').forEach(el => el.remove());
            let stem = clone.textContent.trim();
            stem = stem.replace(/^\\d+\\.\\s*【.+?】\\s*/, '');
            stem = stem.replace(/^\\d+\\.\\s*/, '');
            result.stem = stem;
          }
        } else {
          // 备用：从titleEl中提取
          const clone = titleEl.cloneNode(true);
          clone.querySelectorAll('ul.options, ul.question-options, .question-title-tag').forEach(el => el.remove());
          let stem = clone.textContent.trim();
          stem = stem.replace(/^\\d+\\.\\s*【.+?】\\s*/, '');
          stem = stem.replace(/^\\d+\\.\\s*/, '');
          result.stem = stem;
        }
      } else {
        result.stem = '';
      }
      
      // 提取选项 - ul.question-options 或 ul.options > li.option
      const options = {};
      const optionEls = questionDiv.querySelectorAll('ul.question-options li.option, ul.options li.option');
      optionEls.forEach(opt => {
        const text = opt.textContent.trim();
        const match = text.match(/^([A-E])\\.\\s*(.+)/);
        if (match) {
          options[match[1]] = match[2].trim();
        }
      });
      result.options = options;
      
      // B型题/C型题特殊处理：选项只有字母时，从材料区域提取共享选项
      if (qType === 'B' || qType === 'C') {
        // 检查选项是否只有字母（无实际文本）
        const optionKeys = Object.keys(options);
        const onlyLetters = optionKeys.length > 0 && optionKeys.every(k => {
          const val = options[k];
          return val === k || val.length <= 1;
        });
        
        if (onlyLetters || optionKeys.length === 0) {
          // 尝试从 .material-content 获取共享选项
          const materialEl = document.querySelector('.material-content');
          if (materialEl) {
            const materialText = materialEl.innerText || materialEl.textContent;
            result.material_text = materialText.trim();
            
            // 解析材料中的选项 "A．莪术" 或 "A. 莪术"
            const optionRegex = /([A-E])[.．、]\\s*([^\\n\\r]+)/g;
            let optMatch;
            while ((optMatch = optionRegex.exec(materialText)) !== null) {
              options[optMatch[1]] = optMatch[2].trim();
            }
            result.options = options;
            
            // 提取共享题干（材料中的说明文字，如"根据以下材料，回答41-42题"）
            const stemMatch = materialText.match(/^(.+?)(?=[A-E][.．、])/s);
            if (stemMatch) {
              result.shared_stem = stemMatch[1].trim();
            }
          } else {
            // material-content 不可见，标记需要点击 material-btn
            const materialBtn = document.querySelector('.material-btn');
            if (materialBtn) {
              result.need_material_click = true;
            }
          }
        }
      }
      
      // 提取答案 - 从 .question-common-result 中查找"正确答案：B" 或 "正确答案：A,B,C,E"
      const resultDiv = questionDiv.querySelector('.question-common-result, .question-common-result-wrapper');
      let answer = '';
      if (resultDiv) {
        const text = resultDiv.textContent;
        // 支持逗号分隔的多选答案，如 "正确答案：A,B,C,E"
        const answerMatch = text.match(/正确答案[：:]\\s*([A-E][A-E,\\s]*)/);
        if (answerMatch) {
          answer = answerMatch[1].replace(/[,\\s]/g, '');
        }
      }
      if (!answer) {
        // 备用：从整个题目容器中查找
        const allText = questionDiv.textContent;
        const match = allText.match(/正确答案[：:]\\s*([A-E][A-E,\\s]*)/);
        if (match) {
          answer = match[1].replace(/[,\\s]/g, '');
        }
      }
      result.answer = answer;
      
      // 提取解析 - 从 .question-common-explain 中查找"参考解析："后内容
      let explanation = '';
      const explainDiv = questionDiv.querySelector('.question-common-explain');
      if (explainDiv) {
        const text = explainDiv.textContent;
        const match = text.match(/参考解析[：:]?\\s*([\\s\\S]+?)(?:做题笔记|试题答疑|此解析|对本|$)/);
        if (match) explanation = match[1].trim();
      }
      if (!explanation) {
        // 备用：从整个题目容器中查找
        const allText = questionDiv.textContent;
        const match = allText.match(/参考解析[：:]?\\s*([\\s\\S]+?)(?:做题笔记|试题答疑|此解析|对本|$)/);
        if (match) explanation = match[1].trim();
      }
      result.explanation = explanation;
      
      // 共享题干（配伍题、综合分析题可能有共用材料）
      if (!result.shared_stem) {
        const sharedStemEl = questionDiv.querySelector('.question-shared, .shared-stem, .material, .question-view-material');
        result.shared_stem = sharedStemEl ? sharedStemEl.textContent.trim() : null;
      }
      
      return result;
    }
    """)
    return data


def click_view_answer(page):
    """点击'查看答案'按钮，显示答案和解析
    
    233网校练习模式：.examZt-ltB-ckda 是"查看答案"按钮
    """
    # 先尝试用确定的class
    clicked = page.evaluate("""
    () => {
      const btn = document.querySelector('.examZt-ltB-ckda');
      if (btn && !btn.classList.contains('disabled')) {
        btn.click();
        return true;
      }
      // 备用：查找文本为"查看答案"的可点击元素
      const elements = document.querySelectorAll('button, a, span, div, li');
      for (const el of elements) {
        if (el.textContent.trim() === '查看答案' && el.offsetParent !== null) {
          el.click();
          return true;
        }
      }
      return false;
    }
    """)
    time.sleep(random.uniform(1.0, 2.0))
    return clicked


def click_next_question(page):
    """点击'下一题'按钮
    
    233网校练习模式：.examZt-ltB-next 是"下一题"按钮
    """
    clicked = page.evaluate("""
    () => {
      const nextBtn = document.querySelector('.examZt-ltB-next');
      if (nextBtn && !nextBtn.classList.contains('disabled')) {
        nextBtn.click();
        return true;
      }
      // 备用：查找文本为"下一题"的可点击元素
      const elements = document.querySelectorAll('button, a, span, div, li');
      for (const el of elements) {
        if (el.textContent.trim() === '下一题' && el.offsetParent !== null) {
          if (!el.classList.contains('disabled') && !el.parentElement.classList.contains('disabled')) {
            el.click();
            return true;
          }
        }
      }
      return false;
    }
    """)
    time.sleep(random.uniform(2.0, 4.0))
    return clicked


def click_question_by_number(page, num):
    """通过答题卡点击指定题号
    
    233网校答题卡: .answer-card-body 内的数字按钮
    """
    page.evaluate(f"""
    () => {{
      // 答题卡中的题号按钮
      const selectors = [
        '.answer-card-body span',
        '.answer-card-body div',
        '.card-body span',
        '.question-card span',
        '[class*="answer-card"] span',
        '[class*="answer-card"] div'
      ];
      for (const sel of selectors) {{
        const spans = document.querySelectorAll(sel);
        for (const span of spans) {{
          if (span.textContent.trim() === '{num}' && span.offsetParent !== null) {{
            span.click();
            return true;
          }}
        }}
      }}
      return false;
    }}
    """)
    time.sleep(random.uniform(2.0, 4.0))


def get_current_question_number(page):
    """获取当前题号
    
    233网校页面顶部显示 "0 / 120" 格式的进度
    """
    text = page.evaluate("""
    () => {
      // 查找 "X / Y" 格式的文本
      const elements = document.querySelectorAll('em, span, div, p');
      for (const el of elements) {
        const text = el.textContent.trim();
        if (/^\\d+\\s*\\/\\s*\\d+$/.test(text)) {
          return text;
        }
      }
      return '';
    }
    """)
    match = re.search(r'(\d+)\s*/\s*\d+', text)
    return int(match.group(1)) if match else 0


def human_like_wait(min_sec=3, max_sec=8):
    wait = random.uniform(min_sec, max_sec)
    time.sleep(wait)


# ============================================================
# Agent Worker - 单个智能体爬取一套试卷
# ============================================================

class CrawlAgentWorker:
    """单个爬取智能体，负责爬取一套完整试卷。
    
    仿Claude Code Agent思想：
    - 自主规划：分析进度，决定从哪题开始
    - ReAct模式：Thought → Action → Observation
    - 断点续传：每题立即commit
    - 反爬措施：随机等待、模拟阅读、鼠标轨迹
    """
    
    BATCH_SIZE = 10  # 每爬取10题批量落库一次
    
    def __init__(self, worker_id: str, browser_cdp_url: str = "http://localhost:9222"):
        self.worker_id = worker_id
        self.cdp_url = browser_cdp_url
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.stats = {"success": 0, "fail": 0, "skipped": 0}
        self._batch_buffer = []  # 批量保存缓冲区
    
    def connect(self):
        """连接到已启动的浏览器，创建新Tab"""
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
        self.context = self.browser.contexts[0]
        self.page = self.context.new_page()
        print(f"  [{self.worker_id}] ✅ 已连接浏览器，新Tab已创建")
        return True
    
    def disconnect(self):
        """关闭Tab，断开连接"""
        if self.page:
            try:
                self.page.close()
            except:
                pass
        if self.playwright:
            self.playwright.stop()
        print(f"  [{self.worker_id}] 🔌 已断开浏览器连接")
    
    def navigate_to_paper(self, subject_id: int, year: int):
        """导航到233网校真题做题页面
        
        优先使用试卷直接链接（更可靠），备用方案走列表页
        """
        # 先关闭所有旧的做题标签页（避免复用上一次的标签页）
        for ctx in self.browser.contexts:
            for p in ctx.pages:
                if "extract-question/exercise" in p.url and p != self.page:
                    try:
                        p.close()
                        print(f"  [{self.worker_id}] 🗑️ 已关闭旧做题标签页: {p.url}")
                    except:
                        pass
        
        # 方案1: 使用试卷直接链接
        direct_key = (subject_id, year)
        if direct_key in PAPER_DIRECT_LINKS:
            exam_item_id = PAPER_DIRECT_LINKS[direct_key]
            # 优先使用 wx.233.com 域名（已登录状态），ks.233.com 可能未登录
            direct_url = f"https://wx.233.com/center/paper/detail/{exam_item_id}"
            print(f"  [{self.worker_id}] 🌐 打开试卷直接链接: {direct_url}")
            
            for nav_attempt in range(3):
                try:
                    self.page.goto(direct_url, wait_until="domcontentloaded", timeout=30000)
                    break
                except Exception as e:
                    print(f"  [{self.worker_id}] ⚠️ 导航第{nav_attempt+1}次失败: {e}")
                    if nav_attempt == 2:
                        return False
                    time.sleep(3)
            
            time.sleep(random.uniform(3, 5))
            
            # 试卷详情页 - 点击"练习模式"
            print(f"  [{self.worker_id}] 📄 试卷详情页: {self.page.url}")
            
            # 检查是否已跳转到做题页面
            if "extract-question/exercise" in self.page.url:
                print(f"  [{self.worker_id}] ✅ 直接进入做题页面")
                try:
                    self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=15000)
                    print(f"  [{self.worker_id}] ✅ 已进入做题页面: {self.page.url}")
                    return True
                except:
                    print(f"  [{self.worker_id}] ⚠️ 等待做题页面超时")
            
            # 等待试卷详情页加载 - 按钮可能是"继续练习"、"练习模式"、"开始练习"等
            for detail_attempt in range(3):
                try:
                    # 尝试多种按钮文本
                    self.page.wait_for_selector("text=继续练习", timeout=10000)
                    break
                except:
                    try:
                        self.page.wait_for_selector("text=练习模式", timeout=3000)
                        break
                    except:
                        try:
                            self.page.wait_for_selector("text=开始练习", timeout=3000)
                            break
                        except:
                            pass
                    print(f"  [{self.worker_id}] ⚠️ 等待试卷详情页超时(第{detail_attempt+1}次)")
                    if detail_attempt < 2:
                        time.sleep(3)
                        if "extract-question/exercise" in self.page.url:
                            break
            
            # 检查是否已在做题页面
            if "extract-question/exercise" in self.page.url:
                print(f"  [{self.worker_id}] ✅ 已进入做题页面: {self.page.url}")
                try:
                    self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=15000)
                except:
                    print(f"  [{self.worker_id}] ⚠️ 等待做题页面超时")
                return True
            
            # 点击练习按钮（class: el-tooltip btn btn__red-hollow item）
            # 按钮文本可能是"继续练习"、"练习模式"、"开始练习"等
            clicked = self.page.evaluate("""
            () => {
              // 先尝试精确匹配按钮文本
              const buttons = document.querySelectorAll('button');
              for (const btn of buttons) {
                const text = btn.textContent.trim().replace(/\\s+/g, ' ');
                if ((text === '继续练习' || text === '练习模式' || text === '开始练习' || text.includes('继续 练习')) && btn.offsetParent !== null) {
                  btn.click();
                  return 'clicked: ' + text;
                }
              }
              // 再尝试所有元素
              const elements = document.querySelectorAll('a, span, div');
              for (const el of elements) {
                const text = el.textContent.trim();
                if ((text === '继续练习' || text === '练习模式' || text === '开始练习') && el.offsetParent !== null) {
                  el.click();
                  return 'clicked: ' + text;
                }
              }
              return false;
            }
            """)
            print(f"  [{self.worker_id}] 🔘 点击练习按钮: {clicked}")
            
            time.sleep(random.uniform(3, 5))
            
            # 检查是否在新标签页中打开了做题页面
            # "继续练习"按钮可能使用 window.open 或 target="_blank" 打开新标签
            for ctx in self.browser.contexts:
                for p in ctx.pages:
                    if "extract-question/exercise" in p.url and p != self.page:
                        print(f"  [{self.worker_id}] 📋 发现已打开的做题页面(新标签): {p.url}")
                        self.page = p
                        break
            
            # 检查当前页面是否已跳转
            if "extract-question/exercise" in self.page.url:
                print(f"  [{self.worker_id}] ✅ 已进入做题页面: {self.page.url}")
                try:
                    self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=15000)
                except:
                    print(f"  [{self.worker_id}] ⚠️ 等待题目容器超时，但URL正确")
                return True
            
            # 等待做题页面加载
            for exercise_attempt in range(3):
                try:
                    self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=15000)
                    break
                except:
                    print(f"  [{self.worker_id}] ⚠️ 等待做题页面超时(第{exercise_attempt+1}次)")
                    if exercise_attempt < 2:
                        time.sleep(3)
            
            # 最终验证
            if "extract-question/exercise" not in self.page.url:
                print(f"  [{self.worker_id}] ⚠️ 当前URL不像做题页面: {self.page.url}")
                try:
                    self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=5000)
                except:
                    print(f"  [{self.worker_id}] ❌ 做题页面未加载")
                    return False
            
            print(f"  [{self.worker_id}] ✅ 已进入做题页面: {self.page.url}")
            return True
        
        # 方案2: 走列表页（备用）
        print(f"  [{self.worker_id}] ⚠️ 无直接链接，使用列表页导航")
        list_url = f"https://ks.233.com/{subject_id}/2?t={int(time.time())}"
        print(f"  [{self.worker_id}] 🌐 打开真题列表: {list_url}")
        
        for nav_attempt in range(3):
            try:
                self.page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                break
            except Exception as e:
                print(f"  [{self.worker_id}] ⚠️ 导航第{nav_attempt+1}次失败: {e}")
                if nav_attempt == 2:
                    return False
                time.sleep(3)
        
        time.sleep(random.uniform(3, 5))
        
        # 等待真题列表加载完成
        for wait_attempt in range(3):
            try:
                self.page.wait_for_selector("text=开始做题", timeout=15000)
                break
            except:
                print(f"  [{self.worker_id}] ⚠️ 等待真题列表超时(第{wait_attempt+1}次)，尝试继续...")
                if wait_attempt < 2:
                    self.page.reload(wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(3, 5))
        
        # 在真题列表中找到对应年份的试卷并点击"开始做题"
        clicked = self.page.evaluate(f"""
        () => {{
          const allButtons = document.querySelectorAll('button');
          for (const btn of allButtons) {{
            if (btn.textContent.trim() === '开始做题') {{
              let parent = btn.parentElement;
              while (parent) {{
                const text = parent.textContent;
                if (text.includes('{year}') && text.includes('中药')) {{
                  btn.click();
                  return true;
                }}
                parent = parent.parentElement;
                if (parent && parent.tagName === 'BODY') break;
              }}
            }}
          }}
          const links = document.querySelectorAll('a');
          for (const link of links) {{
            if (link.textContent.includes('{year}') && link.textContent.includes('中药')) {{
              link.click();
              return true;
            }}
          }}
          return false;
        }}
        """)
        
        if not clicked:
            print(f"  [{self.worker_id}] ⚠️ 未找到{year}年试卷")
            return False
        
        time.sleep(random.uniform(3, 5))
        
        # 试卷详情页 - 点击"练习模式"
        print(f"  [{self.worker_id}] 📄 试卷详情页: {self.page.url}")
        
        if "extract-question/exercise" in self.page.url:
            try:
                self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=15000)
            except:
                print(f"  [{self.worker_id}] ⚠️ 等待做题页面超时")
            print(f"  [{self.worker_id}] ✅ 已进入做题页面: {self.page.url}")
            return True
        
        for detail_attempt in range(3):
            try:
                self.page.wait_for_selector("text=练习模式", timeout=10000)
                break
            except:
                print(f"  [{self.worker_id}] ⚠️ 等待试卷详情页超时(第{detail_attempt+1}次)")
                if detail_attempt < 2:
                    time.sleep(3)
                    if "extract-question/exercise" in self.page.url:
                        break
        
        if "extract-question/exercise" in self.page.url:
            print(f"  [{self.worker_id}] ✅ 已进入做题页面: {self.page.url}")
            try:
                self.page.wait_for_selector('.question-view-normal', timeout=15000)
            except:
                print(f"  [{self.worker_id}] ⚠️ 等待做题页面超时")
            return True
        
        # 点击"练习模式"
        self.page.evaluate("""
        () => {
          const elements = document.querySelectorAll('button, a, span, div');
          for (const el of elements) {
            if (el.textContent.trim() === '练习模式' && el.offsetParent !== null) {
              el.click();
              return true;
            }
          }
          return false;
        }
        """)
        
        time.sleep(random.uniform(3, 5))
        
        # 等待做题页面加载
        for exercise_attempt in range(3):
            try:
                self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=15000)
                break
            except:
                print(f"  [{self.worker_id}] ⚠️ 等待做题页面超时(第{exercise_attempt+1}次)")
                if exercise_attempt < 2:
                    time.sleep(3)
        
        if "extract-question/exercise" not in self.page.url:
            print(f"  [{self.worker_id}] ⚠️ 当前URL不像做题页面: {self.page.url}")
            try:
                self.page.wait_for_selector('.question-view-normal, .question-normal', timeout=5000)
            except:
                print(f"  [{self.worker_id}] ❌ 做题页面未加载")
                return False
        
        print(f"  [{self.worker_id}] ✅ 已进入做题页面: {self.page.url}")
        return True
    
    def _flush_batch(self, db, paper_id):
        """将缓冲区中的题目批量写入数据库"""
        if not self._batch_buffer:
            return 0
        
        count = len(self._batch_buffer)
        saved = save_questions_batch(db, paper_id, self._batch_buffer)
        print(f"  [{self.worker_id}] 💾 批量落库: {count}题已写入 (累计成功{self.stats['success']}, 失败{self.stats['fail']})")
        self._batch_buffer.clear()
        return saved
    
    def crawl_paper(self, db, paper, subject_name, subject_id):
        """爬取一套完整试卷（120题），支持断点续传
        
        每10题批量落库一次，避免失败后重头开始。
        """
        paper_id = paper.id
        crawled_numbers = get_crawled_question_numbers(db, paper_id)
        total_crawled = len(crawled_numbers)
        
        print(f"\n  [{self.worker_id}] {'='*50}")
        print(f"  [{self.worker_id}] 📋 开始爬取: {paper.title}")
        print(f"  [{self.worker_id}]    科目: {subject_name} | 年份: {paper.year}")
        print(f"  [{self.worker_id}]    进度: {total_crawled}/{paper.total_questions}")
        print(f"  [{self.worker_id}]    批量大小: {self.BATCH_SIZE}题/次")
        print(f"  [{self.worker_id}] {'='*50}")
        
        if total_crawled >= paper.total_questions:
            print(f"  [{self.worker_id}] ✅ 已完成，跳过")
            return True
        
        # 导航到试卷页面
        if not self.navigate_to_paper(subject_id, paper.year):
            return False
        
        # 找到起始题号
        start_from = 1
        for i in range(1, paper.total_questions + 1):
            if i not in crawled_numbers:
                start_from = i
                break
        
        print(f"  [{self.worker_id}] 🔄 从第{start_from}题开始")
        
        if start_from > 1:
            click_question_by_number(self.page, start_from)
            time.sleep(2)
        
        batch_count = 0  # 当前批次计数
        
        try:
            for q_num in range(start_from, paper.total_questions + 1):
                if q_num in crawled_numbers:
                    self.stats["skipped"] += 1
                    click_next_question(self.page)
                    continue
                
                print(f"  [{self.worker_id}] 📝 第{q_num}/{paper.total_questions}题...")
                
                success = False
                for retry in range(3):
                    try:
                        click_view_answer(self.page)
                        time.sleep(random.uniform(1.0, 2.0))
                        
                        data = extract_question_from_page(self.page)
                        
                        # B型题可能需要点击"查看材料"按钮才能获取共享选项
                        if data.get('need_material_click'):
                            self.page.evaluate("""() => {
                                const btn = document.querySelector('.material-btn');
                                if (btn) btn.click();
                            }""")
                            time.sleep(random.uniform(1.0, 2.0))
                            # 重新提取
                            data = extract_question_from_page(self.page)
                        
                        if data.get('error'):
                            raise Exception(f"提取失败: {data['error']}")
                        if not data.get('stem'):
                            raise Exception("题干为空")
                        if not data.get('answer'):
                            raise Exception("答案为空")
                        
                        # B型/C型题：如果选项仍为空，记录警告但继续
                        q_type = data.get('question_type', 'A')
                        opts = data.get('options', {})
                        if q_type in ('B', 'C') and not opts:
                            print(f"  [{self.worker_id}] ⚠️ 第{q_num}题(B/C型)选项为空")
                        
                        # 加入批量缓冲区，不立即commit
                        self._batch_buffer.append({
                            'question_number': q_num,
                            'question_type': q_type,
                            'stem': data['stem'],
                            'options': opts,
                            'answer': data['answer'],
                            'explanation': data.get('explanation', ''),
                            'shared_stem': data.get('shared_stem')
                        })
                        
                        success = True
                        self.stats["success"] += 1
                        batch_count += 1
                        break
                        
                    except Exception as e:
                        print(f"  [{self.worker_id}] ⚠️ 第{q_num}题第{retry+1}次失败: {e}")
                        if retry < 2:
                            time.sleep(random.uniform(2.0, 4.0))
                            click_question_by_number(self.page, q_num)
                            time.sleep(2)
                
                if not success:
                    self.stats["fail"] += 1
                    print(f"  [{self.worker_id}] ❌ 第{q_num}题失败，跳过")
                    # 失败的也加入缓冲区（占位记录）
                    self._batch_buffer.append({
                        'question_number': q_num,
                        'question_type': 'A',
                        'stem': f"[爬取失败] 第{q_num}题",
                        'options': {},
                        'answer': '',
                        'explanation': ''
                    })
                    batch_count += 1
                
                # 每10题批量落库
                if batch_count >= self.BATCH_SIZE:
                    self._flush_batch(db, paper_id)
                    batch_count = 0
                
                human_like_wait(3, 8)
                
                if q_num < paper.total_questions:
                    click_next_question(self.page)
            
            # 循环结束，flush剩余题目
            self._flush_batch(db, paper_id)
            
        except Exception as e:
            # 异常时也要flush已爬取的数据，避免丢失
            print(f"  [{self.worker_id}] ⚠️ 爬取异常: {e}，正在保存已爬取的数据...")
            self._flush_batch(db, paper_id)
            raise
        
        print(f"  [{self.worker_id}] 📊 完成: 成功{self.stats['success']}, "
              f"失败{self.stats['fail']}, 跳过{self.stats['skipped']}")
        return self.stats["fail"] == 0


# ============================================================
# Task Coordinator - 任务协调器
# ============================================================

class TaskCoordinator:
    """协调多个Agent Worker并行爬取不同试卷。
    
    策略：
    - 将待爬取的试卷放入任务队列
    - N个Worker从队列中取任务执行
    - 每个Worker使用独立的浏览器Tab
    - 试卷间随机休息，避免触发反爬
    """
    
    def __init__(self, num_workers: int = 3, cdp_url: str = "http://localhost:9222"):
        self.num_workers = num_workers
        self.cdp_url = cdp_url
        self.task_queue = queue.Queue()
        self.results = []
        self.lock = threading.Lock()
    
    def add_task(self, paper, subject_name, subject_id):
        """添加爬取任务"""
        self.task_queue.put((paper, subject_name, subject_id))
    
    def worker_loop(self, worker_id: str):
        """Worker主循环：从队列取任务，执行爬取"""
        worker = CrawlAgentWorker(worker_id, self.cdp_url)
        
        try:
            worker.connect()
        except Exception as e:
            print(f"  [{worker_id}] ❌ 连接浏览器失败: {e}")
            return
        
        while True:
            try:
                task = self.task_queue.get_nowait()
            except queue.Empty:
                print(f"  [{worker_id}] 🏁 任务队列已空，退出")
                break
            
            paper, subject_name, subject_id = task
            
            # 每个任务用独立的DB session
            db = SessionLocal()
            try:
                success = worker.crawl_paper(db, paper, subject_name, subject_id)
                with self.lock:
                    self.results.append({
                        "worker": worker_id,
                        "paper_id": paper.id,
                        "paper_title": paper.title,
                        "success": success,
                        "stats": worker.stats.copy()
                    })
                # 重置worker stats
                worker.stats = {"success": 0, "fail": 0, "skipped": 0}
            except Exception as e:
                print(f"  [{worker_id}] ❌ 爬取异常: {e}")
                with self.lock:
                    self.results.append({
                        "worker": worker_id,
                        "paper_id": paper.id,
                        "paper_title": paper.title,
                        "success": False,
                        "error": str(e)
                    })
            finally:
                db.close()
                self.task_queue.task_done()
            
            # 试卷间休息
            time.sleep(random.uniform(5, 15))
        
        worker.disconnect()
    
    def run(self):
        """启动所有Worker并行执行"""
        total_tasks = self.task_queue.qsize()
        print(f"\n🚀 启动 {self.num_workers} 个Agent Worker，共 {total_tasks} 个任务")
        print(f"   浏览器CDP: {self.cdp_url}")
        print()
        
        threads = []
        for i in range(self.num_workers):
            worker_id = f"Worker-{i+1}"
            t = threading.Thread(target=self.worker_loop, args=(worker_id,))
            t.start()
            threads.append(t)
            # 错开启动时间，避免同时连接
            time.sleep(2)
        
        for t in threads:
            t.join()
        
        # 打印最终结果
        print(f"\n{'='*60}")
        print("📊 最终爬取统计:")
        print(f"{'='*60}")
        for r in self.results:
            status = "✅" if r["success"] else "❌"
            stats = r.get("stats", {})
            print(f"  {status} [{r['worker']}] {r['paper_title']}")
            if stats:
                print(f"     成功:{stats.get('success',0)} "
                      f"失败:{stats.get('fail',0)} "
                      f"跳过:{stats.get('skipped',0)}")
        print(f"\n✅ 全部任务完成!")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="233网校真题爬虫 - 多智能体协同版")
    parser.add_argument('--list', action='store_true', help='列出所有试卷和爬取进度')
    parser.add_argument('--create', action='store_true', help='创建所有试卷记录')
    parser.add_argument('--workers', type=int, default=3, help='并行Worker数量（默认3）')
    parser.add_argument('--cdp-url', type=str, default='http://localhost:9222',
                        help='浏览器CDP地址（默认http://localhost:9222）')
    parser.add_argument('--subject', type=str, help='只爬取指定科目')
    parser.add_argument('--year', type=int, help='只爬取指定年份')
    parser.add_argument('--paper-id', type=int, help='只爬取指定试卷ID')
    args = parser.parse_args()
    
    db = SessionLocal()
    
    # 确保表存在
    Base.metadata.create_all(bind=engine, tables=[
        ExamPaper.__table__, ExamQuestion.__table__
    ])
    
    if args.list:
        list_papers(db)
        db.close()
        return
    
    if args.create:
        create_all_papers(db)
        db.close()
        return
    
    # 创建试卷记录
    create_all_papers(db)
    
    # 构建任务列表
    tasks = []
    for config in EXAM_CONFIGS:
        if args.subject and args.subject not in config['subject']:
            continue
        for p_config in config['papers']:
            if args.year and args.year != p_config['year']:
                continue
            paper = db.query(ExamPaper).filter(
                ExamPaper.subject == config['subject'],
                ExamPaper.year == p_config['year']
            ).first()
            if paper:
                if args.paper_id and paper.id != args.paper_id:
                    continue
                crawled = get_crawled_count(db, paper.id)
                if crawled >= paper.total_questions:
                    print(f"  ⏭️  [{paper.id}] {paper.title} 已完成，跳过")
                    continue
                tasks.append((paper, config['subject'], config['subject_id']))
    
    db.close()
    
    if not tasks:
        print("\n没有需要爬取的试卷")
        return
    
    print(f"\n🎯 共 {len(tasks)} 套试卷待爬取:")
    for paper, subject, _ in tasks:
        crawled = get_crawled_count(SessionLocal(), paper.id)
        print(f"  - [{paper.id}] {paper.title} ({crawled}/{paper.total_questions})")
    
    # 启动多智能体协调器
    coordinator = TaskCoordinator(num_workers=args.workers, cdp_url=args.cdp_url)
    for paper, subject, subject_id in tasks:
        coordinator.add_task(paper, subject, subject_id)
    
    coordinator.run()
    
    # 最终统计
    db = SessionLocal()
    list_papers(db)
    db.close()


if __name__ == "__main__":
    main()
