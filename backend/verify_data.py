# -*- coding: utf-8 -*-
"""验证12套试卷题目和答案完整性"""
import sqlite3
import json

db = sqlite3.connect('app/static/qa_database.db')
cur = db.cursor()

# 1. 总体统计
cur.execute('SELECT COUNT(*) FROM exam_questions')
total = cur.fetchone()[0]
print(f'总题数: {total}')

# 2. 每套试卷统计
cur.execute('''
    SELECT p.id, p.subject, p.year, p.title, COUNT(q.id) as q_count
    FROM exam_papers p
    LEFT JOIN exam_questions q ON q.paper_id = p.id
    GROUP BY p.id
    ORDER BY p.id
''')
print()
print('=== 每套试卷题目数 ===')
for row in cur.fetchall():
    print(f'  试卷{row[0]}: {row[1]} {row[2]}年 - {row[4]}题')

# 3. 检查无答案的题目
cur.execute("""
    SELECT paper_id, question_number, question_type FROM exam_questions 
    WHERE answer IS NULL OR answer = '' OR TRIM(answer) = ''
""")
empty_answer = cur.fetchall()
print(f'\n=== 空答案题目数: {len(empty_answer)} ===')
for r in empty_answer[:10]:
    print(f'  试卷{r[0]} 第{r[1]}题 (类型{r[2]})')

# 4. 检查无解析的题目
cur.execute("""
    SELECT paper_id, question_number FROM exam_questions 
    WHERE explanation IS NULL OR explanation = '' OR TRIM(explanation) = ''
""")
empty_exp = cur.fetchall()
print(f'\n=== 空解析题目数: {len(empty_exp)} ===')
for r in empty_exp[:10]:
    print(f'  试卷{r[0]} 第{r[1]}题')

# 5. 检查无选项的题目
cur.execute("""
    SELECT paper_id, question_number, question_type FROM exam_questions 
    WHERE options IS NULL OR options = '' OR options = '{}'
""")
empty_opt = cur.fetchall()
print(f'\n=== 空选项题目数: {len(empty_opt)} ===')
for r in empty_opt[:10]:
    print(f'  试卷{r[0]} 第{r[1]}题 (类型{r[2]})')

# 6. 检查无题干的题目
cur.execute("""
    SELECT paper_id, question_number FROM exam_questions 
    WHERE stem IS NULL OR stem = '' OR TRIM(stem) = ''
""")
empty_stem = cur.fetchall()
print(f'\n=== 空题干题目数: {len(empty_stem)} ===')
for r in empty_stem[:10]:
    print(f'  试卷{r[0]} 第{r[1]}题')

# 7. 检查题号是否连续(1-120)
print('\n=== 题号连续性检查 ===')
cur.execute('SELECT id FROM exam_papers ORDER BY id')
paper_ids = [r[0] for r in cur.fetchall()]
for pid in paper_ids:
    cur.execute('SELECT question_number FROM exam_questions WHERE paper_id=? ORDER BY question_number', (pid,))
    nums = [r[0] for r in cur.fetchall()]
    expected = list(range(1, 121))
    if nums == expected:
        print(f'  试卷{pid}: ✅ 1-120题号连续完整')
    else:
        missing = set(expected) - set(nums)
        extra = set(nums) - set(expected)
        print(f'  试卷{pid}: ❌ 缺失{len(missing)}题, 多出{len(extra)}题')
        if missing:
            print(f'    缺失题号: {sorted(missing)[:20]}')

# 8. 检查答案格式
print('\n=== 答案格式抽样检查 ===')
cur.execute('SELECT paper_id, question_number, question_type, answer FROM exam_questions ORDER BY paper_id, question_number LIMIT 20')
for r in cur.fetchall():
    print(f'  试卷{r[0]} 第{r[1]}题 (类型{r[2]}): 答案={r[3]}')

# 9. 按题型统计答案长度
print('\n=== 各题型答案长度统计 ===')
cur.execute("""
    SELECT question_type, MIN(LENGTH(answer)), MAX(LENGTH(answer)), COUNT(*) 
    FROM exam_questions 
    GROUP BY question_type
""")
for r in cur.fetchall():
    print(f'  类型{r[0]}: 答案长度 {r[1]}-{r[2]} 字符, 共{r[3]}题')

# 10. 检查重复题目(相同试卷相同题号)
print('\n=== 重复题目检查 ===')
cur.execute("""
    SELECT paper_id, question_number, COUNT(*) as cnt
    FROM exam_questions
    GROUP BY paper_id, question_number
    HAVING cnt > 1
""")
dups = cur.fetchall()
print(f'  重复题目数: {len(dups)}')

db.close()
print('\n✅ 验证完成')
