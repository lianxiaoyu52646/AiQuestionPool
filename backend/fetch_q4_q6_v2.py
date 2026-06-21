"""
从233.com获取 Paper 1 (综合2023) Q4/Q6 的解析 - 改进版
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
from playwright.sync_api import sync_playwright
import json
import re
import time

PAPER_URL = "https://wx.233.com/center/paper/detail/430033"

def fetch_explanations():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        
        # 先关闭所有练习标签页（URL包含 extract-question/exercise）
        for pg in context.pages:
            if "extract-question/exercise" in pg.url:
                print(f"🔒 关闭旧练习标签页: {pg.url[:60]}...")
                pg.close()
        
        # 创建新标签页
        page = context.new_page()
        
        try:
            print(f"🌐 打开试卷: {PAPER_URL}")
            page.goto(PAPER_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            # 点击"继续练习"按钮
            practice_btn = page.locator("text=继续练习")
            if practice_btn.count() > 0:
                print("🔘 点击: 继续练习")
                # 尝试等待新标签页
                try:
                    with context.expect_page(timeout=10000) as new_page_info:
                        practice_btn.first.click()
                    exercise_page = new_page_info.value
                    page.close()
                    page = exercise_page
                except:
                    # 如果没有新标签页，可能是在当前页面打开
                    print("  (未检测到新标签页，使用当前页面)")
            else:
                practice_btn = page.locator("text=开始练习")
                if practice_btn.count() > 0:
                    print("🔘 点击: 开始练习")
                    try:
                        with context.expect_page(timeout=10000) as new_page_info:
                            practice_btn.first.click()
                        exercise_page = new_page_info.value
                        page.close()
                        page = exercise_page
                    except:
                        print("  (未检测到新标签页，使用当前页面)")
                else:
                    print("❌ 未找到练习按钮")
                    return None
            
            # 等待做题页面加载
            page.wait_for_selector(".question-view-normal, .question-normal", timeout=15000)
            print(f"✅ 已进入做题页面: {page.url}")
            
            results = {}
            
            for target_qn in [4, 6]:
                print(f"\n📝 获取第{target_qn}题...")
                
                # 使用答题卡跳转
                # 先找到答题卡
                answer_card_items = page.locator(".question-answer-card li")
                if answer_card_items.count() > 0:
                    print(f"  答题卡有 {answer_card_items.count()} 个题号")
                    found = False
                    for i in range(answer_card_items.count()):
                        text = answer_card_items.nth(i).inner_text().strip()
                        if text == str(target_qn):
                            answer_card_items.nth(i).click()
                            found = True
                            print(f"  点击答题卡第 {target_qn} 题")
                            break
                    if not found:
                        print(f"  ⚠️ 答题卡中未找到题号 {target_qn}")
                else:
                    # 尝试使用上一题/下一题按钮
                    print("  ⚠️ 未找到答题卡，尝试使用导航按钮")
                    # 获取当前题号
                    current_qn = 1
                    qnum_el = page.locator(".examTab-num")
                    if qnum_el.count() > 0:
                        qnum_text = qnum_el.first.inner_text().strip()
                        match = re.search(r'(\d+)', qnum_text)
                        if match:
                            current_qn = int(match.group(1))
                    
                    # 导航到目标题
                    while current_qn < target_qn:
                        next_btn = page.locator("text=下一题")
                        if next_btn.count() > 0:
                            next_btn.first.click()
                            time.sleep(0.5)
                            current_qn += 1
                        else:
                            break
                
                time.sleep(1)
                page.wait_for_selector(".question-view-normal, .question-normal", timeout=10000)
                
                # 检查是否需要显示解析
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
                    explain_el = page.locator(".question-common-explain")
                    if explain_el.count() > 0:
                        explain_text = explain_el.first.inner_text().strip()
                
                # 提取答案
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
