"""批量爬取剩余10套试卷"""
import subprocess
import sys
import time

papers = [
    ("中药学专业知识一", 2022),
    ("中药学专业知识一", 2023),
    ("中药学专业知识二", 2020),
    ("中药学专业知识二", 2021),
    ("中药学专业知识二", 2022),
    ("中药学专业知识二", 2023),
    ("中药学综合知识与技能", 2020),
    ("中药学综合知识与技能", 2021),
    ("中药学综合知识与技能", 2022),
    ("中药学综合知识与技能", 2023),
]

python = r"D:\lian\praPro\e\venv\Scripts\python.exe"
script = r"d:\lian\praPro\e\backend\crawl_233_multiagent.py"

for i, (subject, year) in enumerate(papers, 1):
    print(f"\n{'='*60}")
    print(f"  [{i}/10] 爬取: {subject} {year}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(
        [python, script, "--workers", "1", "--subject", subject, "--year", str(year)],
        capture_output=False
    )
    
    if result.returncode == 0:
        print(f"\n✅ 完成: {subject} {year}")
    else:
        print(f"\n❌ 失败: {subject} {year} (exit code: {result.returncode})")
    
    time.sleep(3)

print(f"\n{'='*60}")
print(f"  全部10套试卷爬取完成！")
print(f"{'='*60}")
