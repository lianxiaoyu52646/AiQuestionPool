"""
修复数据质量问题：
1. Paper 5 Q37/Q39/Q40 - 从解析中提取图片题选项
2. Paper 7 Q55/Q56 - 从解析中提取选项（C可能缺失）
3. 212道B/C型题 - 通过相同选项推断group_id和shared_stem
4. Paper 1 Q4/Q6 - 标记为需要重新爬取
"""
import sys
sys.path.insert(0, 'd:/lian/praPro/e/backend')
from app.exam_models import ExamPaper, ExamQuestion
from app.database import SessionLocal
import json
import re

db = SessionLocal()

# ============================================================
# 1. Paper 5 Q37/Q39/Q40 - 从解析中提取图片题选项
# ============================================================
print('=' * 60)
print('1. 修复 Paper 5 (专一2023) Q37/Q39/Q40 图片题选项')
print('=' * 60)

for qn in [37, 39, 40]:
    q = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == 5, 
        ExamQuestion.question_number == qn
    ).first()
    if not q:
        continue
    
    # 解析格式: "A为苦楝皮、B为合欢皮、C为香加皮、D为关黄柏、E为桑白皮。"
    # 或: "A为乳香、B为没药、C为阿魏、D为血竭、E为儿茶。其中..."
    explanation = q.explanation or ''
    
    # 提取 A为XXX、B为XXX 模式
    pattern = r'([A-E])为([^、。；,;]+)'
    matches = re.findall(pattern, explanation)
    
    if matches:
        options = {}
        for letter, text in matches:
            options[letter] = text.strip()
        
        print(f'\nQ{qn}: 提取到 {len(options)} 个选项')
        for k, v in options.items():
            print(f'  {k}: {v}')
        
        if len(options) >= 4:
            q.options = json.dumps(options, ensure_ascii=False)
            db.commit()
            print(f'  ✅ 已更新Q{qn}选项')
        else:
            print(f'  ⚠️ 选项不足4个，未更新')
    else:
        print(f'\nQ{qn}: 未匹配到选项')

# ============================================================
# 2. Paper 7 Q55/Q56 - 从解析中提取选项
# ============================================================
print()
print('=' * 60)
print('2. 修复 Paper 7 (专一2021) Q55/Q56 选项')
print('=' * 60)

for qn in [55, 56]:
    q = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == 7,
        ExamQuestion.question_number == qn
    ).first()
    if not q:
        continue
    
    explanation = q.explanation or ''
    # "A为五环三萜，B为黄酮，D为香豆素，E为木脂素类"
    pattern = r'([A-E])为([^，,。；;]+)'
    matches = re.findall(pattern, explanation)
    
    if matches:
        options = {}
        for letter, text in matches:
            options[letter] = text.strip()
        
        print(f'\nQ{qn}: 提取到 {len(options)} 个选项')
        for k, v in options.items():
            print(f'  {k}: {v}')
        
        if len(options) >= 4:
            q.options = json.dumps(options, ensure_ascii=False)
            # 同时补全 group_id 和 shared_stem
            if not q.group_id:
                q.group_id = 'B4'  # 接着B3之后
                q.shared_stem = '根据下面选项，回答55-56题'
            db.commit()
            print(f'  ✅ 已更新Q{qn}选项和group_id')
        else:
            print(f'  ⚠️ 选项不足4个（可能缺少C），仍更新部分选项')
            q.options = json.dumps(options, ensure_ascii=False)
            if not q.group_id:
                q.group_id = 'B4'
                q.shared_stem = '根据下面选项，回答55-56题'
            db.commit()
            print(f'  ✅ 已更新Q{qn}部分选项和group_id')

# ============================================================
# 3. 212道B/C型题 - 通过相同选项推断group_id
# ============================================================
print()
print('=' * 60)
print('3. 补全缺失group_id的B/C型题')
print('=' * 60)

# 获取所有缺失group_id的B/C型题
missing_qs = db.query(ExamQuestion).filter(
    ExamQuestion.question_type.in_(['B', 'C']),
    ExamQuestion.group_id == None
).order_by(ExamQuestion.paper_id, ExamQuestion.question_number).all()

print(f'缺失group_id的B/C型题: {len(missing_qs)}题')

# 按paper_id分组处理
from collections import defaultdict
by_paper = defaultdict(list)
for q in missing_qs:
    by_paper[q.paper_id].append(q)

total_fixed = 0
for paper_id, qs in sorted(by_paper.items()):
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    print(f'\nPaper {paper_id} ({paper.subject} {paper.year}): {len(qs)}题待修复')
    
    # 获取该试卷所有B/C型题（包括有group_id的）
    all_bc = db.query(ExamQuestion).filter(
        ExamQuestion.paper_id == paper_id,
        ExamQuestion.question_type.in_(['B', 'C'])
    ).order_by(ExamQuestion.question_number).all()
    
    # 按题型分组处理
    for qtype in ['B', 'C']:
        type_qs = [q for q in all_bc if q.question_type == qtype]
        if not type_qs:
            continue
        
        # 找到该题型中已有group_id的最大编号
        existing_groups = [q.group_id for q in type_qs if q.group_id]
        max_group_num = 0
        for g in existing_groups:
            match = re.match(r'[BC](\d+)', g or '')
            if match:
                num = int(match.group(1))
                if num > max_group_num:
                    max_group_num = num
        
        # 按选项内容分组
        groups = []  # list of (options_str, [question_numbers])
        for q in type_qs:
            opts = q.options if isinstance(q.options, str) else json.dumps(q.options, ensure_ascii=False)
            if opts == '{}' or not opts:
                # 选项为空，单独一组
                groups.append((opts, [q.question_number], q))
                continue
            
            # 查找是否已有相同选项的组
            found = False
            for i, (g_opts, g_qns, _) in enumerate(groups):
                if g_opts == opts:
                    g_qns.append(q.question_number)
                    found = True
                    break
            if not found:
                groups.append((opts, [q.question_number], q))
        
        # 为缺失group_id的题分配group_id
        group_counter = max_group_num
        for opts_str, qns, first_q in groups:
            # 检查这组中是否有已有group_id的题
            has_group = False
            for qn in qns:
                q = next(q for q in type_qs if q.question_number == qn)
                if q.group_id:
                    has_group = True
                    existing_gid = q.group_id
                    break
            
            if has_group:
                # 使用已有的group_id
                for qn in qns:
                    q = next(q for q in type_qs if q.question_number == qn)
                    if not q.group_id:
                        q.group_id = existing_gid
                        qns_str = '-'.join(str(n) for n in sorted(qns))
                        q.shared_stem = f'根据以下材料，回答{qns_str}题'
                        total_fixed += 1
            else:
                # 分配新的group_id
                group_counter += 1
                new_gid = f'{qtype}{group_counter}'
                qns_str = '-'.join(str(n) for n in sorted(qns))
                shared_stem = f'根据以下材料，回答{qns_str}题'
                for qn in qns:
                    q = next(q for q in type_qs if q.question_number == qn)
                    if not q.group_id:
                        q.group_id = new_gid
                        q.shared_stem = shared_stem
                        total_fixed += 1
        
        # 输出该题型的分组结果
        missing_type = [q for q in type_qs if not q.group_id]
        fixed_type = [q for q in type_qs if q.group_id]
        if missing_type:
            print(f'  {qtype}型: {len(fixed_type)}有group_id, {len(missing_type)}仍缺失')

db.commit()
print(f'\n总共修复: {total_fixed}题的group_id和shared_stem')

# ============================================================
# 验证修复结果
# ============================================================
print()
print('=' * 60)
print('4. 修复后验证')
print('=' * 60)

# 重新检查
empty_options = db.query(ExamQuestion).filter(
    ExamQuestion.question_type.in_(['B', 'C']),
    ExamQuestion.options == '{}'
).all()
print(f'B/C型题选项为空: {len(empty_options)}题')
for q in empty_options:
    p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
    print(f'  ❌ Paper {p.id} ({p.year}): Q{q.question_number} ({q.question_type}型)')

a_empty = db.query(ExamQuestion).filter(
    ExamQuestion.question_type == 'A',
    ExamQuestion.options == '{}'
).all()
print(f'A型题选项为空: {len(a_empty)}题')
for q in a_empty:
    p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
    print(f'  ⚠️ Paper {p.id} ({p.year}): Q{q.question_number} (A型)')

no_group = db.query(ExamQuestion).filter(
    ExamQuestion.question_type.in_(['B', 'C']),
    ExamQuestion.group_id == None
).all()
print(f'B/C型题缺失group_id: {len(no_group)}题')

no_explain = db.query(ExamQuestion).filter(
    (ExamQuestion.explanation == None) | (ExamQuestion.explanation == '')
).all()
print(f'解析为空: {len(no_explain)}题')
for q in no_explain:
    p = db.query(ExamPaper).filter(ExamPaper.id == q.paper_id).first()
    print(f'  ⚠️ Paper {p.id} ({p.year}): Q{q.question_number} ({q.question_type}型)')

db.close()
print()
print('修复完成!')
