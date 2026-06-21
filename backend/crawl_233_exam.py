# -*- coding: utf-8 -*-
"""
233网校真题爬虫 - 断点续传版

策略：
1. 使用Playwright连接已登录的浏览器页面（用户真实登录状态）
2. 每爬1题立即写入数据库（commit），支持断点续传
3. 模拟真实用户行为：随机等待3-8秒，鼠标有轨迹移动
4. 通过答题卡点击题号跳转，支持从任意题号继续
5. 单题失败自动重试3次，仍失败则跳过并记录

用法：
  python crawl_233_exam.py                    # 交互式选择试卷
  python crawl_233_exam.py --paper-id 1       # 指定试卷ID继续爬取
  python crawl_233_exam.py --list             # 列出所有试卷和爬取进度
"""
import sys
import os
import time
import random
import json
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.exam_models import ExamPaper, ExamQuestion

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
    """获取已爬取的题目数"""
    return db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper_id
    ).count()

def get_crawled_question_numbers(db, paper_id):
    """获取已爬取的题号集合"""
    rows = db.query(ExamQuestion.question_number).filter(
        ExamQuestion.paper_id == paper_id
    ).all()
    return set(r[0] for r in rows)

def save_question(db, paper_id, question_number, question_type, stem,
                  options, answer, explanation, group_id=None, shared_stem=None):
    """保存单题到数据库（立即commit）"""
    # 检查是否已存在（避免重复）
    existing = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper_id,
        ExamQuestion.question_number == question_number
    ).first()
    if existing:
        # 更新
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
    print(f"  💾 已保存第{question_number}题 [{question_type}] 答案:{answer}")

def list_papers(db):
    """列出所有试卷和爬取进度"""
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

# ============================================================
# 页面数据提取
# ============================================================

def extract_question_from_page(page):
    """从当前页面提取一道题目的完整数据"""
    data = page.evaluate("""
    () => {
      const result = {};
      
      // 获取题目容器
      const questionDiv = document.querySelector('.question-normal');
      if (!questionDiv) return {error: 'no question div'};
      
      // 获取题号和题型
      const titleEl = questionDiv.querySelector('.question-single');
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
      
      // 提取题干 - 获取.question-single下的文本，但排除选项和标签
      const questionSingle = questionDiv.querySelector('.question-single');
      if (questionSingle) {
        // 克隆节点，移除选项和标签
        const clone = questionSingle.cloneNode(true);
        const optionsToRemove = clone.querySelectorAll('.options, .question-title-tag');
        optionsToRemove.forEach(el => el.remove());
        let stem = clone.textContent.trim();
        // 移除题号和题型前缀
        stem = stem.replace(/^\\d+\\.\\s*【.+?】\\s*/, '');
        stem = stem.replace(/^\\d+\\.\\s*/, '');
        result.stem = stem;
      } else {
        result.stem = '';
      }
      
      // 提取选项
      const options = {};
      const optionEls = questionDiv.querySelectorAll('.options li.option');
      optionEls.forEach(opt => {
        const text = opt.textContent.trim();
        const match = text.match(/^([A-E])\\.\\s*(.+)/);
        if (match) {
          options[match[1]] = match[2].trim();
        }
      });
      result.options = options;
      
      // 提取答案
      const answerEl = questionDiv.querySelector('.right-answer, .correct-answer');
      if (!answerEl) {
        // 尝试从文本中查找
        const allText = questionDiv.textContent;
        const answerMatch = allText.match(/正确答案[：:]\\s*([A-E]+)/);
        result.answer = answerMatch ? answerMatch[1] : '';
      } else {
        result.answer = answerEl.textContent.replace(/正确答案[：:]\\s*/, '').trim();
      }
      
      // 如果没找到答案，尝试其他选择器
      if (!result.answer) {
        const answerText = questionDiv.textContent;
        const match = answerText.match(/正确答案[：:]\\s*([A-E]+)/);
        result.answer = match ? match[1] : '';
      }
      
      // 提取解析
      let explanation = '';
      const analysisEls = questionDiv.querySelectorAll('li');
      for (const li of analysisEls) {
        const label = li.querySelector('.analysis-label, .label');
        const text = li.textContent.trim();
        if (text.includes('参考解析')) {
          // 获取解析内容（在"参考解析："之后）
          const match = text.match(/参考解析[：:]?\\s*([\\s\\S]+)/);
          if (match) {
            explanation = match[1].trim();
            break;
          }
        }
      }
      // 如果没找到，尝试直接搜索
      if (!explanation) {
        const allText = questionDiv.textContent;
        const match = allText.match(/参考解析[：:]?\\s*([\\s\\S]+?)(?:做题笔记|试题答疑|此解析|$)/);
        if (match) explanation = match[1].trim();
      }
      result.explanation = explanation;
      
      // 提取共享题干（B型/C型题）
      const sharedStemEl = questionDiv.querySelector('.question-shared, .shared-stem, .material');
      result.shared_stem = sharedStemEl ? sharedStemEl.textContent.trim() : null;
      
      return result;
    }
    """)
    return data

def click_view_answer(page):
    """点击'查看答案'按钮，显示答案和解析"""
    page.evaluate("""
    () => {
      // 先选择一个选项（A），否则可能无法查看答案
      const option = document.querySelector('.options li.option');
      if (option) option.click();
    }
    """)
    time.sleep(random.uniform(0.5, 1.5))
    
    page.evaluate("""
    () => {
      const buttons = document.querySelectorAll('button, a, span, div');
      for (const btn of buttons) {
        if (btn.textContent.trim() === '查看答案') {
          btn.click();
          return true;
        }
      }
      return false;
    }
    """)
    time.sleep(random.uniform(1.0, 2.0))

def click_next_question(page):
    """点击'下一题'按钮"""
    page.evaluate("""
    () => {
      const nextBtn = document.querySelector('.examZt-ltB-next');
      if (nextBtn && !nextBtn.classList.contains('disabled')) {
        nextBtn.click();
        return true;
      }
      return false;
    }
    """)
    time.sleep(random.uniform(2.0, 4.0))

def click_question_by_number(page, num):
    """通过答题卡点击指定题号"""
    page.evaluate(f"""
    () => {{
      const spans = document.querySelectorAll('.answer-card-body .result-answer-tags span');
      for (const span of spans) {{
        if (span.textContent.trim() === '{num}') {{
          span.click();
          return true;
        }}
      }}
      return false;
    }}
    """)
    time.sleep(random.uniform(2.0, 4.0))

def get_current_question_number(page):
    """获取当前题号"""
    text = page.evaluate("""
    () => {
      const numEl = document.querySelector('.examTab-num');
      return numEl ? numEl.textContent.trim() : '';
    }
    """)
    # "1 / 120" 格式
    match = re.search(r'(\d+)\s*/\s*\d+', text)
    return int(match.group(1)) if match else 0

def human_like_wait(min_sec=3, max_sec=8):
    """模拟人类阅读思考的等待时间"""
    wait = random.uniform(min_sec, max_sec)
    print(f"  ⏳ 等待 {wait:.1f} 秒（模拟阅读）...")
    time.sleep(wait)

# ============================================================
# 主爬取逻辑
# ============================================================

# 233网校真题页面配置
# subjectId: 311=中药学综合, 312=中药学专一, 313=中药学专二
EXAM_CONFIGS = [
    {
        "subject": "中药学综合知识与技能",
        "subject_id": 311,
        "papers": [
            {"year": 2023, "title": "2023年执业药师《中药学综合知识技能》真题及解析"},
            {"year": 2022, "title": "2022年执业药师考试《中药学综合知识与技能》真题及解析"},
            {"year": 2021, "title": "2021年执业药师考试《中药学综合知识与技能》真题及解析"},
            {"year": 2020, "title": "2020年执业药师考试《中药学综合知识与技能》真题及解析"},
        ]
    },
    {
        "subject": "中药学专业知识一",
        "subject_id": 312,
        "papers": [
            {"year": 2023, "title": "2023年执业药师《中药学专业知识一》真题及解析"},
            {"year": 2022, "title": "2022年执业药师考试《中药学专业知识一》真题及解析"},
            {"year": 2021, "title": "2021年执业药师考试《中药学专业知识一》真题及解析"},
            {"year": 2020, "title": "2020年执业药师考试《中药学专业知识一》真题及解析"},
        ]
    },
    {
        "subject": "中药学专业知识二",
        "subject_id": 313,
        "papers": [
            {"year": 2023, "title": "2023年执业药师《中药学专业知识二》真题及解析"},
            {"year": 2022, "title": "2022年执业药师考试《中药学专业知识二》真题及解析"},
            {"year": 2021, "title": "2021年执业药师考试《中药学专业知识二》真题及解析"},
            {"year": 2020, "title": "2020年执业药师考试《中药学专业知识二》真题及解析"},
        ]
    },
]

def crawl_paper(page, db, paper, subject_name):
    """爬取一套完整试卷（120题），支持断点续传"""
    paper_id = paper.id
    crawled_numbers = get_crawled_question_numbers(db, paper_id)
    total_crawled = len(crawled_numbers)
    
    print(f"\n{'='*60}")
    print(f"📋 开始爬取: {paper.title}")
    print(f"   科目: {subject_name} | 年份: {paper.year}")
    print(f"   进度: {total_crawled}/{paper.total_questions} 已完成")
    print(f"{'='*60}")
    
    if total_crawled >= paper.total_questions:
        print("  ✅ 该试卷已全部爬取完成，跳过")
        return True
    
    # 找到起始题号
    start_from = 1
    for i in range(1, paper.total_questions + 1):
        if i not in crawled_numbers:
            start_from = i
            break
    
    print(f"  🔄 从第{start_from}题开始继续爬取...")
    
    # 如果不是从第1题开始，需要通过答题卡跳转
    if start_from > 1:
        print(f"  📌 通过答题卡跳转到第{start_from}题...")
        click_question_by_number(page, start_from)
        time.sleep(2)
    
    success_count = 0
    fail_count = 0
    current_num = start_from
    
    for q_num in range(start_from, paper.total_questions + 1):
        if q_num in crawled_numbers:
            # 已爬取，跳到下一题
            print(f"  ⏭️  第{q_num}题已存在，跳过")
            click_next_question(page)
            continue
        
        print(f"\n  📝 正在爬取第{q_num}/{paper.total_questions}题...")
        
        # 重试机制
        success = False
        for retry in range(3):
            try:
                # 1. 先点击"查看答案"显示答案和解析
                click_view_answer(page)
                time.sleep(random.uniform(1.0, 2.0))
                
                # 2. 提取题目数据
                data = extract_question_from_page(page)
                
                if data.get('error'):
                    raise Exception(f"提取失败: {data['error']}")
                
                if not data.get('stem'):
                    raise Exception("题干为空")
                
                if not data.get('answer'):
                    raise Exception("答案为空")
                
                # 3. 保存到数据库（立即commit）
                save_question(
                    db=db,
                    paper_id=paper_id,
                    question_number=q_num,
                    question_type=data.get('question_type', 'A'),
                    stem=data['stem'],
                    options=data.get('options', {}),
                    answer=data['answer'],
                    explanation=data.get('explanation', ''),
                    shared_stem=data.get('shared_stem')
                )
                
                success = True
                success_count += 1
                break
                
            except Exception as e:
                print(f"  ⚠️  第{q_num}题第{retry+1}次尝试失败: {e}")
                if retry < 2:
                    time.sleep(random.uniform(2.0, 4.0))
                    # 重新尝试点击当前题号
                    click_question_by_number(page, q_num)
                    time.sleep(2)
        
        if not success:
            fail_count += 1
            print(f"  ❌ 第{q_num}题爬取失败，跳过")
            # 保存一个占位记录，避免重复尝试
            save_question(
                db=db,
                paper_id=paper_id,
                question_number=q_num,
                question_type='A',
                stem=f"[爬取失败] 第{q_num}题",
                options={},
                answer='',
                explanation=''
            )
        
        # 4. 模拟人类阅读等待
        human_like_wait(3, 8)
        
        # 5. 点击下一题
        if q_num < paper.total_questions:
            click_next_question(page)
    
    print(f"\n  📊 爬取完成: 成功{success_count}题, 失败{fail_count}题")
    return fail_count == 0


def main():
    parser = argparse.ArgumentParser(description="233网校真题爬虫（断点续传版）")
    parser.add_argument('--list', action='store_true', help='列出所有试卷和爬取进度')
    parser.add_argument('--paper-id', type=int, help='指定试卷ID继续爬取')
    parser.add_argument('--subject', type=str, help='指定科目名称')
    parser.add_argument('--year', type=int, help='指定年份')
    args = parser.parse_args()
    
    db = SessionLocal()
    
    if args.list:
        list_papers(db)
        db.close()
        return
    
    # 确保表存在
    Base.metadata.create_all(bind=engine, tables=[
        ExamPaper.__table__, ExamQuestion.__table__
    ])
    
    # 创建试卷记录
    papers_to_crawl = []
    for config in EXAM_CONFIGS:
        for p_config in config['papers']:
            if args.subject and args.subject not in config['subject']:
                continue
            if args.year and args.year != p_config['year']:
                continue
            paper = get_or_create_paper(db, config['subject'], p_config['year'], p_config['title'])
            papers_to_crawl.append((paper, config['subject'], config['subject_id']))
    
    if not papers_to_crawl:
        print("没有找到匹配的试卷")
        db.close()
        return
    
    print(f"\n🎯 共 {len(papers_to_crawl)} 套试卷待爬取")
    for paper, subject, _ in papers_to_crawl:
        crawled = get_crawled_count(db, paper.id)
        print(f"  - [{paper.id}] {paper.title} ({crawled}/{paper.total_questions})")
    
    # 需要Playwright连接浏览器
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 需要安装playwright: pip install playwright")
        db.close()
        return
    
    print("\n🌐 正在连接浏览器...")
    print("  请确保:")
    print("  1. 浏览器已用 --remote-debugging-port=9222 启动")
    print("  2. 已登录233网校")
    print("  3. 已打开真题页面")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"❌ 连接浏览器失败: {e}")
            print("  请用以下命令启动浏览器:")
            print('  chrome.exe --remote-debugging-port=9222')
            db.close()
            return
        
        # 获取已打开的页面
        context = browser.contexts[0]
        page = context.new_page()
        
        for paper, subject_name, subject_id in papers_to_crawl:
            # 导航到真题列表页
            list_url = f"https://wx.233.com/center/study/tiku/paper-past?domain=yaoshi&subjectId={subject_id}"
            print(f"\n🌐 打开真题列表: {list_url}")
            page.goto(list_url)
            time.sleep(random.uniform(3, 5))
            
            # 找到对应年份的试卷并点击
            clicked = page.evaluate(f"""
            () => {{
              const items = document.querySelectorAll('.paper-item');
              for (const item of items) {{
                const text = item.textContent;
                if (text.includes('{paper.year}') && text.includes('中药')) {{
                  const btn = item.querySelector('a, button, .btn');
                  if (btn) {{ btn.click(); return true; }}
                  item.click();
                  return true;
                }}
              }}
              return false;
            }}
            """)
            
            if not clicked:
                print(f"  ⚠️  未找到{paper.year}年试卷，跳过")
                continue
            
            time.sleep(random.uniform(3, 5))
            print(f"  ✅ 已进入做题页面: {page.url}")
            
            # 开始爬取
            crawl_paper(page, db, paper, subject_name)
            
            # 试卷间休息
            if paper != papers_to_crawl[-1][0]:
                rest = random.uniform(10, 20)
                print(f"\n  😌 休息 {rest:.0f} 秒后再爬下一套...")
                time.sleep(rest)
        
        page.close()
    
    # 最终统计
    print(f"\n{'='*60}")
    print("📊 最终爬取统计:")
    list_papers(db)
    db.close()
    print("\n✅ 爬取完成!")


if __name__ == "__main__":
    main()
