"""
调试233.com做题页面，找到导航按钮
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        
        # 找到练习页面
        exercise_page = None
        for pg in context.pages:
            if "extract-question/exercise" in pg.url:
                exercise_page = pg
                break
        
        if not exercise_page:
            print("❌ 未找到练习页面")
            return
        
        page = exercise_page
        print(f"当前页面: {page.url}")
        
        # 获取页面中所有可点击元素的文本和类名
        info = page.evaluate("""() => {
            let results = [];
            // 查找所有按钮、链接
            let elements = document.querySelectorAll('a, button, .btn, [onclick], .examTab-btn, .prev, .next');
            for (let el of elements) {
                let text = el.textContent.trim().substring(0, 50);
                let className = el.className;
                let tagName = el.tagName;
                let id = el.id;
                let onclick = el.getAttribute('onclick') || '';
                let href = el.getAttribute('href') || '';
                if (text || className || onclick) {
                    results.push({
                        tag: tagName,
                        text: text,
                        class: className,
                        id: id,
                        onclick: onclick.substring(0, 100),
                        href: href.substring(0, 100),
                        visible: el.offsetParent !== null
                    });
                }
            }
            return results;
        }""")
        
        print(f"\n找到 {len(info)} 个可点击元素:")
        for i, el in enumerate(info):
            if el['visible']:
                print(f"  [{i}] <{el['tag']}> class='{el['class']}' text='{el['text']}' onclick='{el['onclick']}'")
        
        # 也查找答题卡
        print("\n\n查找答题卡相关元素:")
        card_info = page.evaluate("""() => {
            let results = [];
            // 查找答题卡容器
            let selectors = ['.question-answer-card', '.answer-card', '.examTab', '.card-list', '.question-card', 
                           '.answer-sheet', '.answerCard', '.question-tab', '.exam-tab'];
            for (let sel of selectors) {
                let els = document.querySelectorAll(sel);
                for (let el of els) {
                    results.push({
                        selector: sel,
                        class: el.className,
                        children: el.children.length,
                        visible: el.offsetParent !== null,
                        html: el.innerHTML.substring(0, 200)
                    });
                }
            }
            
            // 也查找包含数字的列表
            let allUls = document.querySelectorAll('ul');
            for (let ul of allUls) {
                if (ul.children.length > 20 && ul.children.length < 200) {
                    let firstText = ul.children[0].textContent.trim();
                    if (/^\d+$/.test(firstText)) {
                        results.push({
                            selector: 'ul (numeric items)',
                            class: ul.className,
                            children: ul.children.length,
                            visible: ul.offsetParent !== null,
                            html: ul.innerHTML.substring(0, 200)
                        });
                    }
                }
            }
            
            return results;
        }""")
        
        for item in card_info:
            print(f"  selector={item['selector']}, class={item['class']}, children={item['children']}, visible={item['visible']}")
            print(f"    html: {item['html'][:150]}...")
        
        # 查找上一题/下一题按钮
        print("\n\n查找导航按钮:")
        nav_info = page.evaluate("""() => {
            let results = [];
            let allElements = document.querySelectorAll('*');
            for (let el of allElements) {
                let text = el.textContent.trim();
                if (text === '上一题' || text === '下一题' || text === '上一页' || text === '下一页' ||
                    text === '上题' || text === '下题' || text === '上一个' || text === '下一个') {
                    results.push({
                        tag: el.tagName,
                        text: text,
                        class: el.className,
                        parentClass: el.parentElement ? el.parentElement.className : '',
                        visible: el.offsetParent !== null
                    });
                }
            }
            return results;
        }""")
        
        for item in nav_info:
            print(f"  <{item['tag']}> text='{item['text']}' class='{item['class']}' parentClass='{item['parentClass']}' visible={item['visible']}")
        
        browser.close()

if __name__ == "__main__":
    main()
