"""
从233.com获取 Paper 1 (综合2023) Q4/Q6 的解析 - 直接用JS导航
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
        
        # 先关闭所有练习标签页
        for pg in context.pages:
            if "extract-question/exercise" in pg.url:
                pg.close()
        
        page = context.new_page()
        
        try:
            print(f"🌐 打开试卷: {PAPER_URL}")
            page.goto(PAPER_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            # 点击"继续练习"按钮
            practice_btn = page.locator("text=继续练习")
            if practice_btn.count() > 0:
                print("🔘 点击: 继续练习")
                try:
                    with context.expect_page(timeout=10000) as new_page_info:
                        practice_btn.first.click()
                    exercise_page = new_page_info.value
                    page.close()
                    page = exercise_page
                except:
                    print("  (未检测到新标签页，使用当前页面)")
            
            page.wait_for_selector(".question-view-normal, .question-normal", timeout=15000)
            print(f"✅ 已进入做题页面: {page.url}")
            
            results = {}
            
            for target_qn in [4, 6]:
                print(f"\n📝 获取第{target_qn}题...")
                
                # 使用JavaScript直接跳转到指定题号
                # 233.com的做题页面通常有跳转方法
                # 先尝试点击答题卡中的题号
                # 答题卡可能在底部，需要先展开
                # 尝试多种选择器
                clicked = False
                
                # 方法1: 直接用JS点击答题卡中的题号
                clicked = page.evaluate(f"""() => {{
                    // 查找答题卡
                    let card = document.querySelector('.question-answer-card');
                    if (!card) card = document.querySelector('.answer-card');
                    if (!card) card = document.querySelector('.examTab');
                    if (!card) return 'no_card';
                    
                    // 查找所有题号元素
                    let items = card.querySelectorAll('li, .examTab-num, .num-item');
                    for (let item of items) {{
                        let text = item.textContent.trim();
                        if (text === '{target_qn}') {{
                            item.click();
                            return 'clicked';
                        }}
                    }}
                    return 'not_found_in_card: ' + items.length + ' items';
                }}""")
                print(f"  答题卡结果: {clicked}")
                
                if clicked != 'clicked':
                    # 方法2: 使用上一题按钮导航
                    print(f"  尝试使用导航按钮...")
                    # 获取当前题号
                    current_info = page.evaluate("""() => {
                        let el = document.querySelector('.examTab-num');
                        if (el) return el.textContent.trim();
                        // 尝试其他选择器
                        let el2 = document.querySelector('.current-num');
                        if (el2) return el2.textContent.trim();
                        return 'unknown';
                    }""")
                    print(f"  当前题号: {current_info}")
                    
                    # 提取当前题号数字
                    match = re.search(r'(\d+)', current_info)
                    current_qn = int(match.group(1)) if match else 120
                    
                    # 如果当前题号大于目标，点上一题
                    if current_qn > target_qn:
                        diff = current_qn - target_qn
                        for _ in range(diff):
                            # 尝试多种上一题按钮选择器
                            prev_clicked = page.evaluate("""() => {
                                let btns = document.querySelectorAll('a, button, .btn');
                                for (let btn of btns) {
                                    let text = btn.textContent.trim();
                                    if (text === '上一题' || text === '上一页') {
                                        btn.click();
                                        return true;
                                    }
                                }
                                return false;
                            }""")
                            if not prev_clicked:
                                print(f"  无法找到上一题按钮")
                                break
                            time.sleep(0.3)
                    
                    # 如果当前题号小于目标，点下一题
                    elif current_qn < target_qn:
                        diff = target_qn - current_qn
                        for _ in range(diff):
                            next_clicked = page.evaluate("""() => {
                                let btns = document.querySelectorAll('a, button, .btn');
                                for (let btn of btns) {
                                    let text = btn.textContent.trim();
                                    if (text === '下一题' || text === '下一页') {
                                        btn.click();
                                        return true;
                                    }
                                }
                                return false;
                            }""")
                            if not next_clicked:
                                print(f"  无法找到下一题按钮")
                                break
                            time.sleep(0.3)
                
                time.sleep(1)
                
                # 等待题目加载
                page.wait_for_selector(".question-view-normal, .question-normal", timeout=10000)
                
                # 检查是否需要显示解析
                explain_visible = page.evaluate("""() => {
                    let el = document.querySelector('.question-common-explain .analysis-content');
                    if (el && el.offsetParent !== null) return true;
                    return false;
                }""")
                
                if not explain_visible:
                    # 尝试点击"查看解析"或"查看答案"
                    page.evaluate("""() => {
                        let btns = document.querySelectorAll('a, button, .btn');
                        for (let btn of btns) {
                            let text = btn.textContent.trim();
                            if (text === '查看解析' || text === '查看答案' || text === '解析') {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }""")
                    time.sleep(1)
                
                # 提取所有信息
                info = page.evaluate("""() => {
                    let result = {
                        qnum: '',
                        answer: '',
                        explanation: '',
                        stem: ''
                    };
                    
                    // 题号
                    let qnumEl = document.querySelector('.examTab-num');
                    if (qnumEl) result.qnum = qnumEl.textContent.trim();
                    
                    // 答案
                    let answerEl = document.querySelector('.question-common-result .correctanswer');
                    if (answerEl) result.answer = answerEl.textContent.trim();
                    
                    // 解析
                    let explainEl = document.querySelector('.question-common-explain .analysis-content');
                    if (explainEl) result.explanation = explainEl.textContent.trim();
                    if (!result.explanation) {
                        explainEl = document.querySelector('.question-common-explain');
                        if (explainEl) result.explanation = explainEl.textContent.trim();
                    }
                    
                    // 题干
                    let stemEl = document.querySelector('.question-view-single, .question-single, .question-view-multi, .question-multi');
                    if (stemEl) result.stem = stemEl.textContent.trim().substring(0, 80);
                    
                    return result;
                }""")
                
                print(f"  题号: {info['qnum']}")
                print(f"  题干: {info['stem']}...")
                print(f"  答案: {info['answer']}")
                print(f"  解析: {info['explanation'][:100]}..." if len(info['explanation']) > 100 else f"  解析: {info['explanation']}")
                
                results[target_qn] = info
            
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
        
        if q and data.get('explanation'):
            # 验证题号是否匹配
            qnum_text = data.get('qnum', '')
            match = re.search(r'(\d+)', qnum_text)
            actual_qn = int(match.group(1)) if match else 0
            
            if actual_qn == qn:
                print(f"\n✅ 题号匹配，更新 Q{qn}:")
                print(f"  旧解析: '{q.explanation}'")
                q.explanation = data['explanation']
                print(f"  新解析: '{q.explanation[:80]}...'" if len(q.explanation) > 80 else f"  新解析: '{q.explanation}'")
                db.commit()
                print(f"  ✅ 已更新")
            else:
                print(f"\n⚠️ Q{qn}: 题号不匹配 (期望{qn}, 实际{actual_qn})，跳过")
        else:
            print(f"\n⚠️ Q{qn}: 未获取到解析")
    
    db.close()
    print("\n完成!")


if __name__ == "__main__":
    main()
