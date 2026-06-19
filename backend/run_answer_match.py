# -*- coding: utf-8 -*-
"""
Multi-Agent Answer Matcher
===========================
Uses 10 parallel agents to match 255 unmatched questions with 1197 answers from the answer PDF.

Architecture (inspired by Claude Code):
  - TaskCoordinator: splits unmatched questions into 10 chunks, manages workers
  - AgentWorker: ReAct loop (Thought → Action → Observation → Reflect)
    - Action: fuzzy match by chapter/section/type/number, then fallback to text similarity
    - Observation: validate match quality
    - Reflect: if confidence < threshold, try next strategy
  - MemoryManager: each worker has bounded context (only sees its chunk + relevant answers)
  - Result Aggregator: collects results, deduplicates, writes to DB

Matching strategy (4-tier fallback):
  Tier 1: Exact (chapter, section, question_type, question_number) - normalized
  Tier 2: Fuzzy chapter (similarity > 0.7) + type + number
  Tier 3: Section similarity + type + number (for empty chapter)
  Tier 4: Text similarity (question_text vs explanation) - semantic match

Usage:
  python run_answer_match.py
"""
import os
import sys
import json
import asyncio
import sqlite3
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.answer_parser import parse_answer_pdf

# === Config ===
DB_PATH = os.path.join(os.path.dirname(__file__), "app", "static", "qa_database.db")
ANSWER_PDF_PATH = os.path.join(os.path.dirname(__file__), "app", "static", "uploads", "1200题中药学综合 答案与解析.pdf")
NUM_WORKERS = 10
CONFIDENCE_THRESHOLD = 0.6  # Minimum similarity score to accept a match


# === Utility Functions ===

def normalize_str(s: str) -> str:
    """Normalize string for comparison: remove whitespace, lowercase."""
    if not s:
        return ""
    import re
    return re.sub(r'\s+', '', s).strip().lower()


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio between two strings."""
    a = normalize_str(a)
    b = normalize_str(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Use SequenceMatcher for fuzzy matching
    return SequenceMatcher(None, a, b).ratio()


def chapter_similarity(ch1: str, ch2: str) -> float:
    """Special chapter similarity: handle partial matches like '第二章中医诊断学' vs '第二章中医诊断学基础'."""
    n1 = normalize_str(ch1)
    n2 = normalize_str(ch2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return 0.9
    # Use prefix similarity (chapter names often share prefix)
    prefix_len = 0
    for i in range(min(len(n1), len(n2))):
        if n1[i] == n2[i]:
            prefix_len += 1
        else:
            break
    if prefix_len >= 3:  # At least "第X章" matches
        return 0.7 + 0.2 * (prefix_len / max(len(n1), len(n2)))
    return SequenceMatcher(None, n1, n2).ratio()


def section_similarity(s1: str, s2: str) -> float:
    """Section similarity with partial match handling."""
    n1 = normalize_str(s1)
    n2 = normalize_str(s2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    if n1 in n2 or n2 in n1:
        return 0.85
    return SequenceMatcher(None, n1, n2).ratio()


# === Agent Worker (ReAct Pattern) ===

class AgentWorker:
    """Single agent worker that processes a chunk of unmatched questions.
    
    ReAct Loop:
      Thought: Analyze question metadata (chapter, section, type, number)
      Action: Try matching strategies in order (tier 1 → 2 → 3 → 4)
      Observation: Check match confidence
      Reflect: If low confidence, try next strategy or skip
    """
    
    def __init__(self, worker_id: int, questions: List[Dict], answers: List[Dict]):
        self.worker_id = worker_id
        self.questions = questions  # This worker's chunk of unmatched questions
        self.answers = answers      # All answers from answer PDF
        self.results: List[Dict] = []
        self.logs: List[str] = []
        
        # Build answer index for fast lookup
        self._build_index()
    
    def _build_index(self):
        """Build multi-level index for fast answer lookup."""
        # Index by (normalized_chapter, type, number)
        self.idx_chapter_type_num = defaultdict(list)
        # Index by (type, number)
        self.idx_type_num = defaultdict(list)
        # Index by (normalized_section, type, number)
        self.idx_section_type_num = defaultdict(list)
        # Index by (type, number) with chapter for fuzzy
        self.idx_all_by_type = defaultdict(list)
        
        for ans in self.answers:
            ch = normalize_str(ans.get("chapter", ""))
            sec = normalize_str(ans.get("section", ""))
            qt = ans.get("question_type", "single")
            num = str(ans.get("question_number", ""))
            
            self.idx_chapter_type_num[(ch, qt, num)].append(ans)
            self.idx_type_num[(qt, num)].append(ans)
            self.idx_section_type_num[(sec, qt, num)].append(ans)
            self.idx_all_by_type[qt].append(ans)
    
    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[Worker-{self.worker_id}] {ts} {msg}"
        self.logs.append(entry)
        print(entry)
    
    async def process(self) -> List[Dict]:
        """Process all questions in this worker's chunk.
        
        Each result includes question_id for DB tracking.
        """
        self._log(f"开始处理 {len(self.questions)} 道未匹配题目")
        
        for i, q in enumerate(self.questions):
            result = await self._react_loop(q)
            if result:
                result["question_id"] = q["id"]
                result["question_num"] = q["num"]
                self.results.append(result)
                self._log(f"  [{i+1}/{len(self.questions)}] id={q['id']} Q#{q['num']} [{q['type']}] → 答案={result['answer']} (置信度={result['confidence']:.2f}, 策略={result['strategy']})")
            else:
                self._log(f"  [{i+1}/{len(self.questions)}] id={q['id']} Q#{q['num']} [{q['type']}] → 未找到匹配")
        
        self._log(f"完成: {len(self.results)}/{len(self.questions)} 匹配成功")
        return self.results
    
    async def _react_loop(self, q: Dict) -> Optional[Dict]:
        """ReAct loop: try matching strategies in order."""
        
        # === Thought: Analyze question metadata ===
        q_ch = q.get("chapter", "")
        q_sec = q.get("section", "")
        q_type = q.get("type", "single")
        q_num = str(q.get("num", ""))
        q_text = q.get("text", "")
        
        # === Action Tier 1: Exact (chapter, type, number) ===
        result = self._match_tier1(q_ch, q_type, q_num)
        if result and result["confidence"] >= CONFIDENCE_THRESHOLD:
            return result
        
        # === Action Tier 2: Fuzzy chapter + type + number ===
        result = self._match_tier2(q_ch, q_type, q_num)
        if result and result["confidence"] >= CONFIDENCE_THRESHOLD:
            return result
        
        # === Action Tier 3: Section + type + number (for empty chapter) ===
        if q_sec:
            result = self._match_tier3(q_sec, q_type, q_num)
            if result and result["confidence"] >= CONFIDENCE_THRESHOLD:
                return result
        
        # === Action Tier 4: Type + number (global, pick best by chapter similarity) ===
        result = self._match_tier4(q_ch, q_sec, q_type, q_num)
        if result and result["confidence"] >= CONFIDENCE_THRESHOLD:
            return result
        
        # === Action Tier 5: Text similarity (question_text vs explanation) ===
        if q_text:
            result = self._match_tier5(q_text, q_type, q_num)
            if result and result["confidence"] >= 0.4:  # Lower threshold for text match
                return result
        
        # === Reflect: No match found ===
        return None
    
    def _match_tier1(self, q_ch: str, q_type: str, q_num: str) -> Optional[Dict]:
        """Tier 1: Exact chapter + type + number match."""
        ch_norm = normalize_str(q_ch)
        key = (ch_norm, q_type, q_num)
        candidates = self.idx_chapter_type_num.get(key, [])
        
        if candidates:
            ans = candidates[0]
            return self._make_result(ans, 1.0, "tier1-exact")
        return None
    
    def _match_tier2(self, q_ch: str, q_type: str, q_num: str) -> Optional[Dict]:
        """Tier 2: Fuzzy chapter similarity + type + number."""
        if not q_ch:
            return None
        
        key = (q_type, q_num)
        candidates = self.idx_type_num.get(key, [])
        
        if not candidates:
            return None
        
        best_score = 0.0
        best_ans = None
        
        for ans in candidates:
            score = chapter_similarity(q_ch, ans.get("chapter", ""))
            if score > best_score:
                best_score = score
                best_ans = ans
        
        if best_ans and best_score >= 0.7:
            return self._make_result(best_ans, best_score, "tier2-fuzzy-chapter")
        return None
    
    def _match_tier3(self, q_sec: str, q_type: str, q_num: str) -> Optional[Dict]:
        """Tier 3: Section similarity + type + number."""
        key = (q_type, q_num)
        candidates = self.idx_type_num.get(key, [])
        
        if not candidates:
            return None
        
        best_score = 0.0
        best_ans = None
        
        for ans in candidates:
            a_sec = ans.get("section", "")
            score = section_similarity(q_sec, a_sec)
            if score > best_score:
                best_score = score
                best_ans = ans
        
        if best_ans and best_score >= 0.6:
            return self._make_result(best_ans, best_score, "tier3-section")
        return None
    
    def _match_tier4(self, q_ch: str, q_sec: str, q_type: str, q_num: str) -> Optional[Dict]:
        """Tier 4: Type + number, pick best by combined chapter+section similarity."""
        key = (q_type, q_num)
        candidates = self.idx_type_num.get(key, [])
        
        if not candidates:
            return None
        
        best_score = 0.0
        best_ans = None
        
        for ans in candidates:
            ch_score = chapter_similarity(q_ch, ans.get("chapter", "")) if q_ch else 0.0
            sec_score = section_similarity(q_sec, ans.get("section", "")) if q_sec else 0.0
            # Combined score: weight chapter more than section
            combined = ch_score * 0.6 + sec_score * 0.4
            if q_ch and not q_sec:
                combined = ch_score
            elif not q_ch and q_sec:
                combined = sec_score
            elif not q_ch and not q_sec:
                # No metadata, just pick first candidate with low confidence
                combined = 0.3
            
            if combined > best_score:
                best_score = combined
                best_ans = ans
        
        if best_ans:
            return self._make_result(best_ans, best_score, "tier4-combined")
        return None
    
    def _match_tier5(self, q_text: str, q_type: str, q_num: str) -> Optional[Dict]:
        """Tier 5: Text similarity - match question text with answer explanation."""
        # Get all answers of the same type
        candidates = self.idx_all_by_type.get(q_type, [])
        
        # Also try matching by question number first (narrow down)
        num_candidates = self.idx_type_num.get((q_type, q_num), [])
        
        # If we have number matches, check text similarity among those
        search_pool = num_candidates if num_candidates else candidates[:200]  # Limit search
        
        best_score = 0.0
        best_ans = None
        
        for ans in search_pool:
            # Compare question text with explanation
            exp = ans.get("explanation", "")
            if not exp:
                continue
            
            # Extract key phrases from question text (first 50 chars usually contain the question)
            q_snippet = q_text[:50]
            score = similarity(q_snippet, exp[:100])
            
            if score > best_score:
                best_score = score
                best_ans = ans
        
        if best_ans and best_score >= 0.3:
            return self._make_result(best_ans, best_score * 0.7, "tier5-text")  # Discount text match
        return None
    
    def _make_result(self, ans: Dict, confidence: float, strategy: str) -> Dict:
        """Create a match result dict."""
        return {
            "question_id": None,  # Will be filled by coordinator
            "question_num": None,  # Will be filled
            "answer": ans.get("answer", ""),
            "explanation": ans.get("explanation", ""),
            "confidence": confidence,
            "strategy": strategy,
            "matched_chapter": ans.get("chapter", ""),
            "matched_section": ans.get("section", ""),
        }


# === Task Coordinator ===

class TaskCoordinator:
    """Coordinates multiple agent workers to process unmatched questions in parallel."""
    
    def __init__(self, num_workers: int = 10):
        self.num_workers = num_workers
        self.results: List[Dict] = []
        self.all_logs: List[str] = []
    
    async def run(self, unmatched_questions: List[Dict], all_answers: List[Dict]) -> List[Dict]:
        """Run parallel matching.
        
        Args:
            unmatched_questions: List of unmatched question dicts
            all_answers: List of all answer dicts from answer PDF
            
        Returns:
            List of match results
        """
        print(f"\n{'='*60}")
        print(f"TaskCoordinator: 启动 {self.num_workers} 个Agent并行匹配")
        print(f"  未匹配题目: {len(unmatched_questions)}")
        print(f"  答案总数: {len(all_answers)}")
        print(f"{'='*60}\n")
        
        # Split questions into chunks
        chunk_size = (len(unmatched_questions) + self.num_workers - 1) // self.num_workers
        chunks = []
        for i in range(self.num_workers):
            start = i * chunk_size
            end = start + chunk_size
            chunk = unmatched_questions[start:end]
            if chunk:
                chunks.append(chunk)
        
        print(f"分块: {len(chunks)} 个chunk, 每块约 {chunk_size} 题")
        
        # Create and run workers in parallel
        workers = []
        for i, chunk in enumerate(chunks):
            worker = AgentWorker(i, chunk, all_answers)
            workers.append(worker)
        
        # Run all workers concurrently
        tasks = [worker.process() for worker in workers]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for i, result in enumerate(results_lists):
            if isinstance(result, Exception):
                print(f"[Worker-{i}] ERROR: {result}")
                continue
            self.results.extend(result)
            self.all_logs.extend(workers[i].logs)
        
        print(f"\n{'='*60}")
        print(f"TaskCoordinator: 全部完成")
        print(f"  总匹配: {len(self.results)}/{len(unmatched_questions)}")
        
        # Strategy breakdown
        from collections import Counter
        strategy_counts = Counter(r["strategy"] for r in self.results)
        print(f"  策略分布: {dict(strategy_counts)}")
        
        # Confidence stats
        confs = [r["confidence"] for r in self.results]
        if confs:
            print(f"  置信度: min={min(confs):.2f} max={max(confs):.2f} avg={sum(confs)/len(confs):.2f}")
        
        print(f"{'='*60}\n")
        
        return self.results


# === DB Operations ===

def load_unmatched_questions(db_path: str) -> List[Dict]:
    """Load all unmatched questions from DB."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""SELECT id, question_number, chapter, section, question_type, 
                 question_text FROM questions 
                 WHERE pdf_id=1 AND (answer IS NULL OR answer = '')
                 ORDER BY id""")
    questions = []
    for r in c.fetchall():
        questions.append({
            "id": r[0],
            "num": r[1],
            "chapter": r[2] or "",
            "section": r[3] or "",
            "type": r[4] or "single",
            "text": r[5] or "",
        })
    conn.close()
    return questions


def apply_matches_to_db(db_path: str, matches: List[Dict]):
    """Apply match results to the database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    updated = 0
    skipped = 0
    
    for match in matches:
        qid = match.get("question_id")
        if not qid:
            skipped += 1
            continue
        
        answer = match["answer"]
        explanation = match["explanation"]
        confidence = match["confidence"]
        
        # Only update if confidence is high enough
        if confidence < CONFIDENCE_THRESHOLD:
            skipped += 1
            continue
        
        c.execute(
            "UPDATE questions SET answer = ?, explanation = ? WHERE id = ? AND (answer IS NULL OR answer = '')",
            (answer, explanation, qid)
        )
        if c.rowcount > 0:
            updated += 1
        else:
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nDB更新完成: {updated} 题已更新, {skipped} 题跳过")
    return updated


# === Main ===

async def main():
    print("=" * 60)
    print("多智能体答案匹配系统")
    print("=" * 60)
    
    # 1. Load unmatched questions from DB
    print("\n[1] 加载未匹配题目...")
    questions = load_unmatched_questions(DB_PATH)
    print(f"  未匹配题目: {len(questions)}")
    
    # 2. Parse answer PDF
    print("\n[2] 解析答案PDF...")
    answers = parse_answer_pdf(ANSWER_PDF_PATH)
    print(f"  答案总数: {len(answers)}")
    
    # 3. Run multi-agent matching
    print("\n[3] 启动多智能体匹配...")
    
    # Split questions into chunks
    chunk_size = (len(questions) + NUM_WORKERS - 1) // NUM_WORKERS
    chunks = []
    for i in range(NUM_WORKERS):
        start = i * chunk_size
        end = start + chunk_size
        chunk = questions[start:end]
        if chunk:
            chunks.append(chunk)
    
    print(f"  分块: {len(chunks)} 个chunk, 每块约 {chunk_size} 题")
    
    # Create and run workers in parallel
    workers = []
    for i, chunk in enumerate(chunks):
        worker = AgentWorker(i, chunk, answers)
        workers.append(worker)
    
    # Run all workers concurrently
    tasks = [worker.process() for worker in workers]
    results_lists = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Collect results (question_id already embedded in each result)
    all_matches = []
    for i, result in enumerate(results_lists):
        if isinstance(result, Exception):
            print(f"[Worker-{i}] ERROR: {result}")
            continue
        all_matches.extend(result)
    
    print(f"\n总匹配数: {len(all_matches)}")
    
    # Strategy breakdown
    from collections import Counter
    strategy_counts = Counter(r["strategy"] for r in all_matches)
    print(f"策略分布: {dict(strategy_counts)}")
    confs = [r["confidence"] for r in all_matches]
    if confs:
        print(f"置信度: min={min(confs):.2f} max={max(confs):.2f} avg={sum(confs)/len(confs):.2f}")
    
    # 4. Apply to DB
    print("\n[4] 写入数据库...")
    updated = apply_matches_to_db(DB_PATH, all_matches)
    
    # 5. Final stats
    print("\n[5] 最终统计...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM questions WHERE pdf_id=1 AND answer IS NOT NULL AND answer != ''")
    total_answered = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM questions WHERE pdf_id=1")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM questions WHERE pdf_id=1 AND (answer IS NULL OR answer = '')")
    still_unmatched = c.fetchone()[0]
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"最终结果:")
    print(f"  总题目: {total}")
    print(f"  有答案: {total_answered} ({total_answered/total*100:.1f}%)")
    print(f"  无答案: {still_unmatched} ({still_unmatched/total*100:.1f}%)")
    print(f"  本次新增: {updated}")
    print(f"{'='*60}")
    
    # Save match report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_unmatched": len(questions),
        "total_matched": len(all_matches),
        "total_updated": updated,
        "still_unmatched": still_unmatched,
        "matches": all_matches,
    }
    report_path = os.path.join(os.path.dirname(__file__), "match_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n匹配报告已保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
