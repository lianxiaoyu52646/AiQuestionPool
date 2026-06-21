"""测试修改后的extract_question_from_page函数"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

sys.path.insert(0, 'd:/lian/praPro/e/backend')
from crawl_233_multiagent import extract_question_from_page, click_view_answer, click_question_by_number

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0]

page = None
for p in context.pages:
    if "extract-question/exercise" in p.url:
        page = p
        break

if not page:
    print("no page found")
    pw.stop()
    exit()

print(f"URL: {page.url}")
time.sleep(3)

# 测试1: B型题（Q41）
print("\n=== 测试B型题 Q41 ===")
click_question_by_number(page, 41)
time.sleep(2)
click_view_answer(page)
time.sleep(2)

data = extract_question_from_page(page)
print(f"题号: {data.get('question_number')}")
print(f"题型: {data.get('question_type')}")
print(f"题干: {data.get('stem', '')[:60]}")
print(f"选项: {json.dumps(data.get('options', {}), ensure_ascii=False)[:200]}")
print(f"答案: {data.get('answer')}")
print(f"共享题干: {data.get('shared_stem', '')[:100] if data.get('shared_stem') else 'None'}")
print(f"解析: {data.get('explanation', '')[:60]}")
print(f"need_material_click: {data.get('need_material_click', False)}")

# 测试2: B型题（Q42）
print("\n=== 测试B型题 Q42 ===")
click_question_by_number(page, 42)
time.sleep(2)
click_view_answer(page)
time.sleep(2)

data = extract_question_from_page(page)
print(f"题号: {data.get('question_number')}")
print(f"题型: {data.get('question_type')}")
print(f"题干: {data.get('stem', '')[:60]}")
print(f"选项: {json.dumps(data.get('options', {}), ensure_ascii=False)[:200]}")
print(f"答案: {data.get('answer')}")
print(f"共享题干: {data.get('shared_stem', '')[:100] if data.get('shared_stem') else 'None'}")

# 测试3: X型题（Q111）
print("\n=== 测试X型题 Q111 ===")
click_question_by_number(page, 111)
time.sleep(2)
click_view_answer(page)
time.sleep(2)

data = extract_question_from_page(page)
print(f"题号: {data.get('question_number')}")
print(f"题型: {data.get('question_type')}")
print(f"题干: {data.get('stem', '')[:60]}")
print(f"选项: {json.dumps(data.get('options', {}), ensure_ascii=False)[:200]}")
print(f"答案: {data.get('answer')}")
print(f"答案长度: {len(data.get('answer', ''))}")

# 测试4: A型题（Q1）
print("\n=== 测试A型题 Q1 ===")
click_question_by_number(page, 1)
time.sleep(2)
click_view_answer(page)
time.sleep(2)

data = extract_question_from_page(page)
print(f"题号: {data.get('question_number')}")
print(f"题型: {data.get('question_type')}")
print(f"题干: {data.get('stem', '')[:60]}")
print(f"选项: {json.dumps(data.get('options', {}), ensure_ascii=False)[:200]}")
print(f"答案: {data.get('answer')}")

pw.stop()
print("\n✅ 测试完成")
