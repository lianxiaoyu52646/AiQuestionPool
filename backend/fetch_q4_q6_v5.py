"""
从233.com获取 Paper 1 (综合2023) Q4/Q6 的解析 - v5
使用"上一题"按钮导航，从题干提取实际题号
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
from playwright.sync_api import sync_playwright
import re
import time

PAPER_URL = "https://wx.233.com/center/paper/detail/430033"

def get_current_qnum(page):
    """从题干文本提取实际题号"""
    info = page.evaluate("""() => {
        // 从题干中提取题号
        let stemEl = document.querySelector('.question-view-single, .question-single, .question-view-multi, .question-multi, .question-view-normal, .question-normal');
        let stem = stemEl ? stemEl.textContent.trim() : '';
        // 也获取examTab-num
        let numEl = document.querySelector('.examTab-num');
        let numText = numEl ? numEl.textContent.trim() : '';
        return {stem: stem.substring(0, 200), numText: numText};
    }""")
    # 从题干中提取题号，如 "4. 【最佳选择题】..."
    match = re.match(r'^(\d+)[.．、]', info['stem'].strip())
    if match:
        return int(match.group(1)), info['stem']
    return 0, info['stem']

def get_question_data(page):
    """提取当前页面的题目数据"""
    info = page.evaluate("""() => {
        let result = {answer: '', explanation: '', stem: ''};
        
        let answerEl = document.querySelector('.question-common-result .correctanswer');
        if (answerEl) result.answer = answerEl.textContent.trim();
        
        // 尝试多个解析选择器
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
    return info

def show_analysis(page):
    """显示解析"""
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

def navigate_to_q(page, target_qn):
    """导航到指定题号"""
    current_qn, stem = get_current_qnum(page)
    print(f"  当前题号: {current_qn} (指示器显示: {stem[:30]}...)")
    
    if current_qn == target_qn:
        return True
    
    if current_qn > target_qn:
        # 需要后退
        attempts = 0
        max_attempts = 200
        while current_qn > target_qn and attempts < max_attempts:
            # 点击"上一题"按钮
            clicked = page.evaluate("""() => {
                let btn = document.querySelector('.examZt-ltB-prev');
                if (btn && btn.offsetParent !== null) {
                    btn.click();
                    return true;
                }
                btn = document.querySelector('.examZt-ltB-l');
                if (btn && btn.offsetParent !== null) {
                    btn.click();
                    return true;
                }
                return false;
            }""")
            
            if not clicked:
                # 后备：键盘
                page.keyboard.press("ArrowLeft")
            
            time.sleep(0.15)
            attempts += 1
            
            if attempts % 10 == 0:
                current_qn, stem = get_current_qnum(page)
                print(f"  进度: 第{current_qn}题 (已后退{attempts}步)")
                if current_qn == 0:
                    # 题号提取失败，检查是否已到达
                    print(f"  题干: {stem[:60]}...")
                    # 从题干检查
                    match = re.match(r'^(\d+)[.．、]', stem.strip())
                    if match:
                        current_qn = int(match.group(1))
        
        # 最终检查
        current_qn, stem = get_current_qnum(page)
        print(f"  最终题号: {current_qn}")
        return current_qn == target_qn
    
    elif current_qn < target_qn:
        # 需要前进
        attempts = 0
        max_attempts = 200
        while current_qn < target_qn and attempts < max_attempts:
            # 查找"下一题"按钮
            clicked = page.evaluate("""() => {
                let btns = document.querySelectorAll('div, a, button');
                for (let btn of btns) {
                    let text = btn.textContent.trim();
                    if (text === '下一题' && btn.offsetParent !== null && btn.className) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
            
            if not clicked:
                page.keyboard.press("ArrowRight")
            
            time.sleep(0.15)
            attempts += 1
            
            if attempts % 10 == 0:
                current_qn, stem = get_current_qnum(page)
                print(f"  进度: 第{current_qn}题 (已前进{attempts}步)")
        
        current_qn, stem = get_current_qnum(page)
        return current_qn == target_qn
    
    return False


def main():
    print("从233.com获取 Paper 1 (综合2023) Q4/Q6 解析 (v5)")
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
            
            # 先调查答题卡结构
            print("\n🔍 调查答题卡结构...")
            card_info = page.evaluate("""() => {
                let card = document.querySelector('.question-answer-card');
                if (!card) return null;
                
                function getStructure(el, depth=0) {
                    let result = {
                        tag: el.tagName,
                        class: el.className,
                        text: el.textContent.trim().substring(0, 100),
                        children: []
                    };
                    if (depth < 3) {
                        for (let child of el.children) {
                            result.children.push(getStructure(child, depth + 1));
                        }
                    }
                    return result;
                }
                
                return getStructure(card);
            }""")
            
            if card_info:
                print(f"答题卡根: <{card_info['tag']}> class='{card_info['class']}'")
                for child in card_info.get('children', []):
                    print(f"  <{child['tag']}> class='{child['class']}' text='{child['text'][:50]}' children={len(child.get('children', []))}")
                    for grandchild in child.get('children', []):
                        print(f"    <{grandchild['tag']}> class='{grandchild['class']}' text='{grandchild['text'][:50]}' children={len(grandchild.get('children', []))}")
            
            results = {}
            
            for target_qn in [4, 6]:
                print(f"\n{'='*40}")
                print(f"📝 导航到第{target_qn}题...")
                
                success = navigate_to_q(page, target_qn)
                time.sleep(1)
                
                # 显示解析
                show_analysis(page)
                
                # 提取数据
                data = get_question_data(page)
                current_qn, stem = get_current_qnum(page)
                
                print(f"  实际题号: {current_qn}")
                print(f"  题干: {data['stem'][:80]}...")
                print(f"  答案: {data['answer']}")
                expl = data['explanation']
                print(f"  解析: {expl[:120]}..." if len(expl) > 120 else f"  解析: {expl}")
                
                results[target_qn] = {
                    'actual_qn': current_qn,
                    'data': data
                }
            
        finally:
            page.close()
            browser.close()
    
    # 更新数据库
    print(f"\n{'='*40}")
    print("更新数据库...")
    db = SessionLocal()
    
    for target_qn, result in results.items():
        actual_qn = result['actual_qn']
        data = result['data']
        
        q = db.query(ExamQuestion).filter(
            ExamQuestion.paper_id == 1,
            ExamQuestion.question_number == target_qn
        ).first()
        
        if not q:
            print(f"⚠️ Q{target_qn}: 数据库中未找到")
            continue
        
        if actual_qn != target_qn:
            print(f"⚠️ Q{target_qn}: 导航到的题号({actual_qn})不匹配，但尝试从题干验证")
            # 检查题干是否匹配
            if target_qn == 4 and '糖耐量' in data['stem']:
                print(f"  题干匹配Q4 (包含'糖耐量')")
                actual_qn = target_qn
            elif target_qn == 6 and '足厥阴' in data['stem']:
                print(f"  题干匹配Q6 (包含'足厥阴')")
                actual_qn = target_qn
            else:
                print(f"  题干不匹配，跳过。题干: {data['stem'][:60]}")
                continue
        
        if data.get('explanation') and len(data['explanation']) > 10:
            print(f"\n✅ 更新 Q{target_qn}:")
            print(f"  旧解析: '{q.explanation}'")
            q.explanation = data['explanation']
            print(f"  新解析: '{q.explanation[:80]}...'" if len(q.explanation) > 80 else f"  新解析: '{q.explanation}'")
            db.commit()
            print(f"  ✅ 已保存")
        else:
            print(f"⚠️ Q{target_qn}: 解析为空或太短")
    
    db.close()
    print("\n完成!")


if __name__ == "__main__":
    main()
