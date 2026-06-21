"""调试233网校B型题DOM结构"""
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
    print("未找到练习页面")
    # 列出所有页面
    for i, p in enumerate(context.pages):
        print(f"  Page {i}: {p.url[:100]}")
    browser.close()
    pw.stop()
    exit()

print(f"URL: {page.url}")
time.sleep(3)

# 点击查看答案
page.evaluate("""() => {
    const btn = document.querySelector('.examZt-ltB-ckda');
    if (btn) btn.click();
}""")
time.sleep(2)

# 获取第1题完整HTML
html1 = page.evaluate("""() => {
    const q = document.querySelector('.question-normal');
    if (!q) return 'no';
    return q.outerHTML;
}""")
with open('d:/lian/praPro/e/backend/debug_q1.html', 'w', encoding='utf-8') as f:
    f.write(html1)
print(f"第1题HTML已保存，长度: {len(html1)}")

# 点击下一题直到第41题
for i in range(40):
    page.evaluate("""() => {
        const btn = document.querySelector('.examZt-ltB-next');
        if (btn && !btn.classList.contains('disabled')) btn.click();
    }""")
    time.sleep(0.5)

time.sleep(2)

# 检查当前题号
num = page.evaluate("""() => {
    const el = document.querySelector('.examTab-num');
    return el ? el.textContent.trim() : '';
}""")
print(f"当前题号: {num}")

# 点击查看答案
page.evaluate("""() => {
    const btn = document.querySelector('.examZt-ltB-ckda');
    if (btn) btn.click();
}""")
time.sleep(2)

# 获取第41题完整HTML
html41 = page.evaluate("""() => {
    const q = document.querySelector('.question-normal');
    if (!q) return 'no';
    return q.outerHTML;
}""")
with open('d:/lian/praPro/e/backend/debug_q41.html', 'w', encoding='utf-8') as f:
    f.write(html41)
print(f"第41题HTML已保存，长度: {len(html41)}")

# 获取第42题
page.evaluate("""() => {
    const btn = document.querySelector('.examZt-ltB-next');
    if (btn && !btn.classList.contains('disabled')) btn.click();
}""")
time.sleep(2)
page.evaluate("""() => {
    const btn = document.querySelector('.examZt-ltB-ckda');
    if (btn) btn.click();
}""")
time.sleep(2)

html42 = page.evaluate("""() => {
    const q = document.querySelector('.question-normal');
    if (!q) return 'no';
    return q.outerHTML;
}""")
with open('d:/lian/praPro/e/backend/debug_q42.html', 'w', encoding='utf-8') as f:
    f.write(html42)
print(f"第42题HTML已保存，长度: {len(html42)}")

# 也获取一道X型题（第111题）
for i in range(69):
    page.evaluate("""() => {
        const btn = document.querySelector('.examZt-ltB-next');
        if (btn && !btn.classList.contains('disabled')) btn.click();
    }""")
    time.sleep(0.3)
time.sleep(2)
page.evaluate("""() => {
    const btn = document.querySelector('.examZt-ltB-ckda');
    if (btn) btn.click();
}""")
time.sleep(2)

num2 = page.evaluate("""() => {
    const el = document.querySelector('.examTab-num');
    return el ? el.textContent.trim() : '';
}""")
print(f"X型题题号: {num2}")

html111 = page.evaluate("""() => {
    const q = document.querySelector('.question-normal');
    if (!q) return 'no';
    return q.outerHTML;
}""")
with open('d:/lian/praPro/e/backend/debug_q111.html', 'w', encoding='utf-8') as f:
    f.write(html111)
print(f"第111题(X型)HTML已保存，长度: {len(html111)}")

# 不调用browser.close()，只stop playwright
pw.stop()
print("完成")
