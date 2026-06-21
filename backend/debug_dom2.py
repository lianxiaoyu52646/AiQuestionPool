"""调试B型题共享选项位置"""
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

# 导航到第41题
for i in range(40):
    page.evaluate("""() => {
        const btn = document.querySelector('.examZt-ltB-next');
        if (btn && !btn.classList.contains('disabled')) btn.click();
    }""")
    time.sleep(0.3)
time.sleep(2)

# 点击查看答案
page.evaluate("""() => {
    const btn = document.querySelector('.examZt-ltB-ckda');
    if (btn) btn.click();
}""")
time.sleep(2)

# 获取题目区域和周围所有内容
full_html = page.evaluate("""() => {
    // 获取题目区域及其上方所有兄弟元素
    const ct = document.querySelector('.examZt-ltCt');
    if (!ct) return 'no examZt-ltCt';
    return ct.innerHTML;
}""")

with open('d:/lian/praPro/e/backend/debug_full_page.html', 'w', encoding='utf-8') as f:
    f.write(full_html)
print(f"页面内容已保存，长度: {len(full_html)}")

# 也获取整个question区域的外层HTML（包含共享材料）
question_area = page.evaluate("""() => {
    // 查找包含question-normal的父容器
    const q = document.querySelector('.question-normal');
    if (!q) return 'no question';
    // 获取父容器
    let parent = q.parentElement;
    while (parent && parent.tagName !== 'BODY') {
        if (parent.classList.contains('examZt-ltCt') || 
            parent.classList.contains('question-view') ||
            parent.classList.contains('question-list')) {
            return parent.innerHTML;
        }
        parent = parent.parentElement;
    }
    // 如果没找到，返回question-normal的前一个兄弟+自身
    let html = '';
    let prev = q.previousElementSibling;
    while (prev) {
        html = prev.outerHTML + html;
        prev = prev.previousElementSibling;
    }
    return html + q.outerHTML;
}""")

with open('d:/lian/praPro/e/backend/debug_question_area.html', 'w', encoding='utf-8') as f:
    f.write(question_area)
print(f"题目区域已保存，长度: {len(question_area)}")

# 查找包含选项文本的元素
options_info = page.evaluate("""() => {
    const result = [];
    // 查找所有包含"寒邪"或"止咳"等文本的元素（B型题选项通常包含这些）
    const allEls = document.querySelectorAll('*');
    for (const el of allEls) {
        const text = el.textContent.trim();
        // 查找包含A. xxx B. xxx格式的元素
        if (/^[A-E][.．、]\\s*\\S+/.test(text) && text.length < 200 && el.children.length <= 2) {
            const cls = el.className || '';
            const tag = el.tagName;
            result.push({tag, class: cls, text: text.substring(0, 100)});
        }
    }
    return result.slice(0, 20);
}""")

with open('d:/lian/praPro/e/backend/debug_options_info.json', 'w', encoding='utf-8') as f:
    json.dump(options_info, f, ensure_ascii=False, indent=2)
print(f"选项信息已保存，共{len(options_info)}条")

# 查找共享材料/共享题干
shared_info = page.evaluate("""() => {
    const result = [];
    const selectors = [
        '.question-shared', '.shared-stem', '.material', 
        '.question-view-material', '.question-batch', '.question-view-batch',
        '.question-material', '.batch-options', '.shared-options',
        '.question-common-stem', '.question-group', '.question-view-group',
        '[class*="shared"]', '[class*="material"]', '[class*="batch"]', '[class*="group"]'
    ];
    for (const sel of selectors) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
            result.push({
                selector: sel,
                tag: el.tagName,
                class: el.className,
                text: el.textContent.substring(0, 200).trim(),
                html: el.outerHTML.substring(0, 500)
            });
        }
    }
    return result;
}""")

with open('d:/lian/praPro/e/backend/debug_shared_info.json', 'w', encoding='utf-8') as f:
    json.dump(shared_info, f, ensure_ascii=False, indent=2)
print(f"共享区域信息已保存，共{len(shared_info)}条")

pw.stop()
print("完成")
