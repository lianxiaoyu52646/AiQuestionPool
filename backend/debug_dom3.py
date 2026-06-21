"""调试B型题 - 用答题卡点击Q41"""
from playwright.sync_api import sync_playwright
import json, time

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0]

page = None
for p in context.pages:
    if "extract-question/exercise" in p.url:
        page = p
        break

if not page:
    print("no page")
    pw.stop()
    exit()

print(f"URL: {page.url}")
time.sleep(3)

# 用答题卡点击第41题
clicked = page.evaluate("""() => {
    // 答题卡数字按钮
    const cards = document.querySelectorAll('.question-answer-card .card-item, .answer-card .card-item, [class*="card"] [class*="item"]');
    if (cards.length > 0) return 'found cards: ' + cards.length;
    
    // 尝试其他选择器
    const nums = document.querySelectorAll('.examZt-rtCz-ul li, .answer-card li, [class*="answer-card"] li');
    return 'nums: ' + nums.length;
}""")
print(f"答题卡: {clicked}")

# 获取答题卡HTML结构
card_html = page.evaluate("""() => {
    const card = document.querySelector('.question-answer-card') || document.querySelector('[class*="answer-card"]') || document.querySelector('.examZt-rt');
    if (!card) return 'no card';
    return card.outerHTML.substring(0, 3000);
}""")
with open('d:/lian/praPro/e/backend/debug_card.html', 'w', encoding='utf-8') as f:
    f.write(card_html)
print(f"答题卡HTML已保存，长度: {len(card_html)}")

# 点击第41题
page.evaluate("""() => {
    const card = document.querySelector('.question-answer-card') || document.querySelector('[class*="answer-card"]');
    if (!card) return false;
    const items = card.querySelectorAll('li, span, a, div');
    for (const item of items) {
        if (item.textContent.trim() === '41') {
            item.click();
            return true;
        }
    }
    return false;
}""")
time.sleep(3)

# 点击查看答案
page.evaluate("""() => {
    const btn = document.querySelector('.examZt-ltB-ckda');
    if (btn) btn.click();
}""")
time.sleep(3)

# 获取题号
num = page.evaluate("""() => {
    const el = document.querySelector('.examTab-num');
    return el ? el.textContent.trim() : '';
}""")
print(f"当前题号: {num}")

# 获取整个做题区域HTML
full_html = page.evaluate("""() => {
    const ct = document.querySelector('.examZt-ltCt');
    if (!ct) return 'no';
    return ct.innerHTML;
}""")
with open('d:/lian/praPro/e/backend/debug_btype_full.html', 'w', encoding='utf-8') as f:
    f.write(full_html)
print(f"B型题页面HTML已保存，长度: {len(full_html)}")

# 获取question-normal及其所有兄弟元素
siblings_html = page.evaluate("""() => {
    const q = document.querySelector('.question-normal') || document.querySelector('.question-view-normal');
    if (!q) return 'no question';
    
    // 获取父容器
    let parent = q.parentElement;
    let html = '';
    if (parent) {
        html = parent.innerHTML;
    }
    return html;
}""")
with open('d:/lian/praPro/e/backend/debug_btype_parent.html', 'w', encoding='utf-8') as f:
    f.write(siblings_html)
print(f"B型题父容器HTML已保存，长度: {len(siblings_html)}")

# 查找包含选项文本的元素（如"寒邪"、"止咳"等）
options_text = page.evaluate("""() => {
    const result = [];
    const allEls = document.querySelectorAll('li.option, .option');
    for (const el of allEls) {
        result.push({
            class: el.className,
            text: el.textContent.trim().substring(0, 100),
            parent: el.parentElement ? el.parentElement.className : ''
        });
    }
    return result;
}""")
with open('d:/lian/praPro/e/backend/debug_btype_options.json', 'w', encoding='utf-8') as f:
    json.dump(options_text, f, ensure_ascii=False, indent=2)
print(f"选项信息已保存，共{len(options_text)}条")

pw.stop()
print("完成")
