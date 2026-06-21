"""
从233.com获取 Paper 1 (综合2023) Q4/Q6 的解析
使用键盘快捷键或直接URL导航
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
from playwright.sync_api import sync_playwright
import re
import time

PAPER_URL = "https://wx.233.com/center/paper/detail/430033"

def fetch_explanations():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        
        # 关闭所有练习标签页
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
            
            # 先查看页面结构，找到导航方式
            print("\n🔍 查找导航元素...")
            nav_info = page.evaluate("""() => {
                let results = [];
                let allElements = document.querySelectorAll('a, button, .btn, [onclick], span, div');
                for (let el of allElements) {
                    let text = el.textContent.trim();
                    if (text === '上一题' || text === '下一题' || text === '上一页' || text === '下一页' ||
                        text === '上题' || text === '下题' || text === '上一个' || text === '下一个' ||
                        text === '前一道' || text === '下一道') {
                        results.push({
                            tag: el.tagName,
                            text: text,
                            class: el.className,
                            id: el.id,
                            visible: el.offsetParent !== null,
                            rect: el.getBoundingClientRect ? {
                                x: el.getBoundingClientRect().x,
                                y: el.getBoundingClientRect().y
                            } : null
                        });
                    }
                }
                
                // 也查找答题卡
                let cardSelectors = ['.question-answer-card', '.answer-card', '.examTab', '.card-list', 
                                   '.question-card', '.answer-sheet', '.answerCard', '.question-tab'];
                let cardFound = null;
                for (let sel of cardSelectors) {
                    let el = document.querySelector(sel);
                    if (el) {
                        cardFound = {
                            selector: sel,
                            class: el.className,
                            children: el.children.length,
                            visible: el.offsetParent !== null
                        };
                        break;
                    }
                }
                
                // 查找所有ul中有数字li的
                let numericUls = [];
                let uls = document.querySelectorAll('ul');
                for (let ul of uls) {
                    if (ul.children.length >= 10 && ul.children.length <= 200) {
                        let firstText = ul.children[0].textContent.trim();
                        if (/^\d+$/.test(firstText)) {
                            numericUls.push({
                                class: ul.className,
                                parentClass: ul.parentElement ? ul.parentElement.className : '',
                                children: ul.children.length,
                                firstText: firstText,
                                visible: ul.offsetParent !== null
                            });
                        }
                    }
                }
                
                return {navButtons: results, answerCard: cardFound, numericUls: numericUls};
            }""")
            
            print(f"导航按钮: {len(nav_info['navButtons'])}个")
            for btn in nav_info['navButtons']:
                print(f"  <{btn['tag']}> text='{btn['text']}' class='{btn['class']}' visible={btn['visible']}")
            
            print(f"\n答题卡: {nav_info['answerCard']}")
            print(f"数字UL: {nav_info['numericUls']}")
            
            results = {}
            
            for target_qn in [4, 6]:
                print(f"\n📝 获取第{target_qn}题...")
                
                # 方法1: 尝试用键盘快捷键（左箭头导航到上一题）
                # 当前在第120题，需要导航到第4题
                current_info = page.evaluate("""() => {
                    let el = document.querySelector('.examTab-num');
                    return el ? el.textContent.trim() : 'unknown';
                }""")
                match = re.search(r'(\d+)', current_info)
                current_qn = int(match.group(1)) if match else 120
                print(f"  当前题号: {current_qn}")
                
                if current_qn > target_qn:
                    diff = current_qn - target_qn
                    print(f"  需要后退 {diff} 题")
                    for i in range(diff):
                        # 尝试按左箭头键
                        page.keyboard.press("ArrowLeft")
                        time.sleep(0.2)
                        
                        # 也尝试点击找到的导航按钮
                        # 键盘导航已经足够，不需要额外点击按钮
                        
                        if i % 20 == 0:
                            # 检查当前题号
                            cur = page.evaluate("""() => {
                                let el = document.querySelector('.examTab-num');
                                return el ? el.textContent.trim() : 'unknown';
                            }""")
                            match2 = re.search(r'(\d+)', cur)
                            cur_qn = int(match2.group(1)) if match2 else current_qn - i
                            print(f"  进度: 第{cur_qn}题 (已后退{i+1}步)")
                
                time.sleep(1)
                page.wait_for_selector(".question-view-normal, .question-normal", timeout=10000)
                
                # 检查是否需要显示解析
                explain_visible = page.evaluate("""() => {
                    let el = document.querySelector('.question-common-explain .analysis-content');
                    if (el && el.offsetParent !== null) return true;
                    return false;
                }""")
                
                if not explain_visible:
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
                
                # 提取信息
                info = page.evaluate("""() => {
                    let result = {qnum: '', answer: '', explanation: '', stem: ''};
                    let qnumEl = document.querySelector('.examTab-num');
                    if (qnumEl) result.qnum = qnumEl.textContent.trim();
                    let answerEl = document.querySelector('.question-common-result .correctanswer');
                    if (answerEl) result.answer = answerEl.textContent.trim();
                    let explainEl = document.querySelector('.question-common-explain .analysis-content');
                    if (explainEl) result.explanation = explainEl.textContent.trim();
                    if (!result.explanation) {
                        explainEl = document.querySelector('.question-common-explain');
                        if (explainEl) result.explanation = explainEl.textContent.trim();
                    }
                    let stemEl = document.querySelector('.question-view-single, .question-single, .question-view-multi, .question-multi');
                    if (stemEl) result.stem = stemEl.textContent.trim().substring(0, 100);
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
