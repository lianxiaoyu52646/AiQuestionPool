"""
从233.com获取 Paper 1 (综合2023) Q4/Q6 的解析 - v6
通过答题卡数字按钮直接跳转到指定题号
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
from playwright.sync_api import sync_playwright
import re
import time

PAPER_URL = "https://wx.233.com/center/paper/detail/430033"

def main():
    print("从233.com获取 Paper 1 (综合2023) Q4/Q6 解析 (v6)")
    print("=" * 60)
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        
        # 关闭旧的练习页面
        for pg in context.pages:
            if "extract-question/exercise" in pg.url:
                pg.close()
        
        page = context.new_page()
        
        try:
            print(f"🌐 打开试卷: {PAPER_URL}")
            page.goto(PAPER_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            # 点击"继续练习"
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
            
            # 调查答题卡中的数字按钮
            print("\n🔍 调查答题卡数字按钮...")
            card_items = page.evaluate("""() => {
                let cardBody = document.querySelector('.answer-card-body');
                if (!cardBody) return [];
                
                // 查找所有包含数字的元素
                let items = [];
                let allEls = cardBody.querySelectorAll('*');
                for (let el of allEls) {
                    let text = el.textContent.trim();
                    // 纯数字且1-3位数
                    if (/^\\d+$/.test(text) && text.length <= 3) {
                        items.push({
                            tag: el.tagName,
                            class: el.className,
                            text: text,
                            onclick: el.getAttribute('onclick') || '',
                            visible: el.offsetParent !== null
                        });
                    }
                }
                return items;
            }""")
            
            print(f"答题卡中找到 {len(card_items)} 个数字元素:")
            for item in card_items[:10]:
                print(f"  <{item['tag']}> class='{item['class']}' text='{item['text']}' onclick='{item['onclick']}'")
            if len(card_items) > 10:
                print(f"  ... 共{len(card_items)}个")
            
            results = {}
            
            for target_qn in [4, 6]:
                print(f"\n{'='*40}")
                print(f"📝 点击答题卡跳转到第{target_qn}题...")
                
                # 点击答题卡中的对应数字
                clicked = page.evaluate(f"""() => {{
                    let cardBody = document.querySelector('.answer-card-body');
                    if (!cardBody) return false;
                    
                    let allEls = cardBody.querySelectorAll('*');
                    for (let el of allEls) {{
                        let text = el.textContent.trim();
                        if (text === '{target_qn}' && el.offsetParent !== null) {{
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }}""")
                
                print(f"  点击结果: {clicked}")
                time.sleep(2)
                
                # 确保解析显示
                page.evaluate("""() => {
                    let btns = document.querySelectorAll('a, button, .btn, div, span');
                    for (let btn of btns) {
                        let text = btn.textContent.trim();
                        if ((text === '查看解析' || text === '查看答案' || text === '解析') && btn.offsetParent !== null) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                time.sleep(1)
                
                # 提取数据
                data = page.evaluate("""() => {
                    let result = {qnum: '', answer: '', explanation: '', stem: ''};
                    
                    let numEl = document.querySelector('.examTab-num');
                    if (numEl) result.qnum = numEl.textContent.trim();
                    
                    let answerEl = document.querySelector('.question-common-result .correctanswer');
                    if (answerEl) result.answer = answerEl.textContent.trim();
                    
                    let explainEl = document.querySelector('.question-common-explain .analysis-content');
                    if (explainEl) result.explanation = explainEl.textContent.trim();
                    if (!result.explanation) {
                        explainEl = document.querySelector('.question-common-explain');
                        if (explainEl) result.explanation = explainEl.textContent.trim();
                    }
                    if (!result.explanation) {
                        explainEl = document.querySelector('.analysis-content');
                        if (explainEl) result.explanation = explainEl.textContent.trim();
                    }
                    
                    let stemEl = document.querySelector('.question-view-single, .question-single, .question-view-multi, .question-multi, .question-view-normal, .question-normal');
                    if (stemEl) result.stem = stemEl.textContent.trim();
                    
                    return result;
                }""")
                
                print(f"  指示器: {data['qnum']}")
                print(f"  题干: {data['stem'][:100]}...")
                print(f"  答案: {data['answer']}")
                expl = data['explanation']
                print(f"  解析: {expl[:150]}..." if len(expl) > 150 else f"  解析: {expl}")
                
                results[target_qn] = data
            
        finally:
            page.close()
            browser.close()
    
    # 更新数据库
    print(f"\n{'='*40}")
    print("更新数据库...")
    db = SessionLocal()
    
    for target_qn, data in results.items():
        q = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == 1,
            ExamQuestion.question_number == target_qn
        ).first()
        
        if not q:
            print(f"⚠️ Q{target_qn}: 数据库中未找到")
            continue
        
        # 验证题干匹配
        stem_match = False
        if target_qn == 4 and '糖耐量' in data['stem']:
            stem_match = True
            print(f"✅ Q4 题干匹配 (包含'糖耐量')")
        elif target_qn == 6 and '足厥阴' in data['stem']:
            stem_match = True
            print(f"✅ Q6 题干匹配 (包含'足厥阴')")
        elif target_qn == 6 and '经脉' in data['stem'] and '脏腑' in data['stem']:
            stem_match = True
            print(f"✅ Q6 题干匹配 (包含'经脉'和'脏腑')")
        
        if not stem_match:
            print(f"⚠️ Q{target_qn}: 题干不匹配，跳过")
            print(f"  题干: {data['stem'][:80]}")
            continue
        
        if data.get('explanation') and len(data['explanation']) > 10:
            print(f"\n✅ 更新 Q{target_qn}:")
            print(f"  旧解析: '{q.explanation}'")
            q.explanation = data['explanation']
            print(f"  新解析: '{q.explanation[:100]}...'" if len(q.explanation) > 100 else f"  新解析: '{q.explanation}'")
            db.commit()
            print(f"  ✅ 已保存")
        else:
            print(f"⚠️ Q{target_qn}: 解析为空或太短")
    
    db.close()
    print("\n完成!")


if __name__ == "__main__":
    main()
