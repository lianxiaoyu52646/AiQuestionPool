"""调试B型题 - 查看材料"""
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

# 点击查看材料
page.evaluate("""() => {
    const btn = document.querySelector('.material-btn');
    if (btn) { btn.click(); return true; }
    return false;
}""")
time.sleep(3)

# 获取材料内容
material_html = page.evaluate("""() => {
    // 查找材料弹窗
    const selectors = [
        '.material-content', '.material-box', '.material-popup',
        '.question-material', '.shared-material', '.view-material',
        '[class*="material"]:not(.material-btn)',
        '.el-dialog', '.el-drawer', '.modal', '.popup'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null) {
            return {selector: sel, html: el.innerHTML.substring(0, 5000)};
        }
    }
    return 'no material found';
}""")

if isinstance(material_html, dict):
    with open('d:/lian/praPro/e/backend/debug_material.html', 'w', encoding='utf-8') as f:
        f.write(material_html['html'])
    print(f"材料HTML已保存 (selector: {material_html['selector']})，长度: {len(material_html['html'])}")
else:
    print(material_html)
    
    # 尝试查找所有可见的弹窗/浮层
    popups = page.evaluate("""() => {
        const result = [];
        const els = document.querySelectorAll('[class*="material"], [class*="popup"], [class*="dialog"], [class*="drawer"], [class*="modal"]');
        for (const el of els) {
            const style = window.getComputedStyle(el);
            if (style.display !== 'none' && style.visibility !== 'hidden') {
                result.push({
                    tag: el.tagName,
                    class: el.className,
                    text: el.textContent.substring(0, 200).trim(),
                    visible: el.offsetParent !== null
                });
            }
        }
        return result.slice(0, 20);
    }""")
    with open('d:/lian/praPro/e/backend/debug_popups.json', 'w', encoding='utf-8') as f:
        json.dump(popups, f, ensure_ascii=False, indent=2)
    print(f"弹窗信息已保存，共{len(popups)}条")

# 也获取整个页面的HTML（查找材料区域）
full_page = page.evaluate("""() => {
    return document.body.innerHTML;
}""")
# 搜索包含选项文本的区域
import re
# 查找包含 "A." 后面跟文字的模式
matches = re.findall(r'[^>]*A[.．、]\s*[^<]{5,50}', full_page)
with open('d:/lian/praPro/e/backend/debug_material_search.txt', 'w', encoding='utf-8') as f:
    for m in matches[:20]:
        f.write(m + '\n---\n')
print(f"材料搜索结果已保存，共{len(matches)}条")

pw.stop()
print("完成")
