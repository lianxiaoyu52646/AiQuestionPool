"""诊断脚本：检查试卷详情页的页面结构"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        
        # 使用已有的Tab或创建新的
        if browser.contexts:
            context = browser.contexts[0]
            page = await context.new_page()
        else:
            context = await browser.new_context()
            page = await context.new_page()
        
        # 访问试卷直接链接
        url = "https://ks.233.com/tiku/exam/item/411721"
        print(f"访问: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        import asyncio as aio
        await aio.sleep(5)
        
        print(f"当前URL: {page.url}")
        print(f"页面标题: {await page.title()}")
        
        # 获取页面所有按钮和链接文本
        buttons = await page.query_selector_all("button, a, .btn, [class*='btn'], [class*='button']")
        print(f"\n找到 {len(buttons)} 个按钮/链接:")
        for btn in buttons[:50]:
            text = await btn.text_content()
            cls = await btn.get_attribute("class")
            href = await btn.get_attribute("href")
            tag = await btn.evaluate("el => el.tagName")
            if text and text.strip():
                print(f"  <{tag}> class='{cls}' text='{text.strip()[:50]}' href='{href}'")
        
        # 获取页面所有包含"练习"、"做题"、"开始"的元素
        print("\n搜索包含关键字的元素:")
        keywords = ["练习", "做题", "开始", "进入", "exam", "exercise"]
        for kw in keywords:
            elements = await page.query_selector_all(f"text={kw}")
            for el in elements[:5]:
                text = await el.text_content()
                cls = await el.get_attribute("class")
                tag = await el.evaluate("el => el.tagName")
                if text:
                    print(f"  关键字'{kw}': <{tag}> class='{cls}' text='{text.strip()[:80]}'")
        
        # 获取页面body的前2000个字符
        body_text = await page.evaluate("document.body.innerText.substring(0, 3000)")
        print(f"\n页面文本前3000字符:\n{body_text}")
        
        # 获取页面HTML前5000个字符
        html = await page.evaluate("document.body.innerHTML.substring(0, 5000)")
        print(f"\n页面HTML前5000字符:\n{html}")
        
        await page.close()

asyncio.run(main())
