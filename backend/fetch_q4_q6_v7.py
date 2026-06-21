"""
重新获取Q4/Q6的完整解析，包括"参考解析"后面的内容
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamQuestion
from app.database import SessionLocal
from playwright.sync_api import sync_playwright
import re
import time

PAPER_URL = "https://wx.233.com/center/paper/detail/430033"

def main():
    print("重新获取Q4/Q6完整解析 (v7)")
    print("=" * 60)
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        
        for pg in context.pages:
            if "extract-question/exercise" in pg.url:
                pg.close()
        
        page = context.new_page()
        
        try:
            print(f"🌐 打开试卷: {PAPER_URL}")
            page.goto(PAPER_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
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
                print(f"\n{'='*40}")
                print(f"📝 跳转到第{target_qn}题...")
                
                # 点击答题卡
                page.evaluate(f"""() => {{
                    let cardBody = document.querySelector('.answer-card-body');
                    if (!cardBody) return false;
                    let allEls = cardBody.querySelectorAll('span');
                    for (let el of allEls) {{
                        if (el.textContent.trim() === '{target_qn}' && el.offsetParent !== null) {{
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }}""")
                time.sleep(2)
                
                # 获取完整解析区域HTML
                explain_html = page.evaluate("""() => {
                    let explainEl = document.querySelector('.question-common-explain');
                    if (!explainEl) return '';
                    return explainEl.innerHTML;
                }""")
                
                # 也获取纯文本
                explain_text = page.evaluate("""() => {
                    let explainEl = document.querySelector('.question-common-explain');
                    if (!explainEl) return '';
                    return explainEl.innerText;
                }""")
                
                # 获取所有子元素
                children_info = page.evaluate("""() => {
                    let explainEl = document.querySelector('.question-common-explain');
                    if (!explainEl) return [];
                    let results = [];
                    for (let child of explainEl.children) {
                        results.push({
                            tag: child.tagName,
                            class: child.className,
                            text: child.innerText.substring(0, 300),
                            visible: child.offsetParent !== null
                        });
                    }
                    return results;
                }""")
                
                print(f"  解析区域子元素 ({len(children_info)}个):")
                for child in children_info:
                    print(f"    <{child['tag']}> class='{child['class']}' visible={child['visible']}")
                    print(f"      text: {child['text'][:200]}")
                
                # 获取analysis-content的完整内容
                analysis_content = page.evaluate("""() => {
                    let el = document.querySelector('.analysis-content');
                    if (!el) return '';
                    return el.innerText;
                }""")
                
                print(f"\n  analysis-content完整文本:")
                print(f"  {analysis_content[:500]}")
                
                results[target_qn] = {
                    'explain_text': explain_text,
                    'analysis_content': analysis_content
                }
            
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
            continue
        
        # 使用完整解析文本，清理广告
        text = data['analysis_content'] or data['explain_text']
        # 清理
        text = re.sub(r'举一反三.*$', '', text, flags=re.DOTALL)
        text = re.sub(r'V2会员专享.*$', '', text, flags=re.DOTALL)
        text = re.sub(r'开始练\s*习.*$', '', text, flags=re.DOTALL)
        text = re.sub(r'当前可体验.*$', '', text, flags=re.DOTALL)
        text = re.sub(r'根据错题.*$', '', text, flags=re.DOTALL)
        text = re.sub(r'此解析是否帮到了你.*$', '', text, flags=re.DOTALL)
        text = re.sub(r'看懂没看懂.*$', '', text, flags=re.DOTALL)
        text = re.sub(r'\s+', ' ', text).strip()
        
        print(f"\nQ{target_qn}:")
        print(f"  最终解析: {text[:300]}")
        
        if text and len(text) > 10:
            q.explanation = text
            db.commit()
            print(f"  ✅ 已保存")
    
    db.close()
    print("\n完成!")

if __name__ == "__main__":
    main()
