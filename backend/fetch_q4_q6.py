"""
从233.com获取 Paper 1 (综合2023) Q4/Q6 的解析
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
from playwright.sync_api import sync_playwright
import json
import re
import time

# 233.com 综合2023 试卷链接
PAPER_URL = "https://wx.233.com/center/paper/detail/430033"

def fetch_explanations():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        
        # 创建新标签页
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        
        try:
            # 打开试卷详情页
            print(f"🌐 打开试卷: {PAPER_URL}")
            page.goto(PAPER_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            # 点击"继续练习"按钮
            practice_btn = page.locator("text=继续练习")
            if practice_btn.count() > 0:
                print("🔘 点击: 继续练习")
                # 监听新标签页
                with context.expect_page(timeout=10000) as new_page_info:
                    practice_btn.first.click()
                exercise_page = new_page_info.value
                page.close()
                page = exercise_page
            else:
                # 尝试"开始练习"
                practice_btn = page.locator("text=开始练习")
                if practice_btn.count() > 0:
                    print("🔘 点击: 开始练习")
                    with context.expect_page(timeout=10000) as new_page_info:
                        practice_btn.first.click()
                    exercise_page = new_page_info.value
                    page.close()
                    page = exercise_page
                else:
                    print("❌ 未找到练习按钮")
                    return
            
            page.wait_for_selector(".question-view-normal, .question-normal", timeout=15000)
            print(f"✅ 已进入做题页面: {page.url}")
            
            results = {}
            
            for target_qn in [4, 6]:
                print(f"\n📝 获取第{target_qn}题...")
                
                # 导航到目标题目
                # 使用答题卡跳转
                answer_card = page.locator(".question-answer-card")
                if answer_card.count() > 0:
                    # 点击对应题号
                    item = page.locator(f".question-answer-card .examTab-num:has-text('{target_qn}')")
                    if item.count() == 0:
                        # 尝试其他选择器
                        items = page.locator(".question-answer-card li")
                        for i in range(items.count()):
                            text = items.nth(i).inner_text().strip()
                            if text == str(target_qn):
                                items.nth(i).click()
                                break
                    else:
                        item.first.click()
                    
                    time.sleep(1)
                
                # 等待题目加载
                page.wait_for_selector(".question-view-normal, .question-normal", timeout=10000)
                
                # 检查是否需要显示解析
                # 先看解析是否已显示
                explain_el = page.locator(".question-common-explain .analysis-content")
                if explain_el.count() == 0:
                    # 尝试点击"查看解析"按钮
                    analysis_btn = page.locator("text=查看解析")
                    if analysis_btn.count() > 0:
                        analysis_btn.first.click()
                        time.sleep(1)
                    
                    # 或者点击"查看答案"
                    answer_btn = page.locator("text=查看答案")
                    if answer_btn.count() > 0:
                        answer_btn.first.click()
                        time.sleep(1)
                
                # 等待解析出现
                try:
                    page.wait_for_selector(".question-common-explain .analysis-content", timeout=5000)
                except:
                    pass
                
                # 提取解析
                explain_text = ""
                explain_el = page.locator(".question-common-explain .analysis-content")
                if explain_el.count() > 0:
                    explain_text = explain_el.first.inner_text().strip()
                
                if not explain_text:
                    # 尝试其他选择器
                    explain_el = page.locator(".question-common-explain")
                    if explain_el.count() > 0:
                        explain_text = explain_el.first.inner_text().strip()
                
                # 也提取答案
                answer_text = ""
                answer_el = page.locator(".question-common-result .correctanswer")
                if answer_el.count() > 0:
                    answer_text = answer_el.first.inner_text().strip()
                
                # 提取题号
                qnum_text = ""
                qnum_el = page.locator(".examTab-num")
                if qnum_el.count() > 0:
                    qnum_text = qnum_el.first.inner_text().strip()
                
                print(f"  题号: {qnum_text}")
                print(f"  答案: {answer_text}")
                print(f"  解析: {explain_text[:100]}..." if len(explain_text) > 100 else f"  解析: {explain_text}")
                
                results[target_qn] = {
                    'explanation': explain_text,
                    'answer_text': answer_text,
                    'qnum_text': qnum_text
                }
            
            return results
            
        finally:
            page.close()
            browser.close()


def main():
    print("从233.com获取 Paper 1 (综合2023) Q4/Q6 解析")
    print("=" * 60)
    
    results = fetch_explanations()
    
    if not results:
        print("❌ 未能获取数据")
        return
    
    # 更新数据库
    db = SessionLocal()
    
    for qn, data in results.items():
        q = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == 1,
            ExamQuestion.question_number == qn
        ).first()
        
        if q and data['explanation']:
            print(f"\n更新 Q{qn}:")
            print(f"  旧解析: '{q.explanation}'")
            q.explanation = data['explanation']
            print(f"  新解析: '{q.explanation[:80]}...'" if len(q.explanation) > 80 else f"  新解析: '{q.explanation}'")
            db.commit()
            print(f"  ✅ 已更新")
        else:
            print(f"\n⚠️ Q{qn}: 未获取到解析或题目不存在")
    
    db.close()
    print("\n完成!")


if __name__ == "__main__":
    main()
