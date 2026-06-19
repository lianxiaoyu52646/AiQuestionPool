# -*- coding: utf-8 -*-
"""Multi-agent parallel parser with ReAct pattern.

Architecture (inspired by Claude Code / harness engineering):
- TaskCoordinator: manages chunk queue, assigns to workers, tracks progress
- AgentWorker: each worker runs ReAct loop (Thought → Action → Observation)
- MemoryManager: compresses old messages when token threshold exceeded

Breakpoint resume: all state is in DB (agent_sessions + task_states).
If interrupted, re-run picks up from where it left off.
"""
import os
import json
import asyncio
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    AgentSession, TaskState, AgentMessage,
    PDFFile, Question, Category
)
from app.services.kimi_service import KimiService
from app.services.memory_service import MemoryManager, estimate_tokens


class AgentWorker:
    """A single agent worker that processes chunks using ReAct pattern.
    
    ReAct loop:
    1. Thought: analyze the chunk text, decide strategy
    2. Action: call GLM API to extract questions
    3. Observation: check result quality, decide if retry needed
    4. Loop back to Thought if needed, or finish
    """

    def __init__(self, worker_id: str, kimi: KimiService, memory: MemoryManager,
                 api_semaphore: asyncio.Semaphore = None):
        self.worker_id = worker_id
        self.kimi = kimi
        self.memory = memory
        self._api_semaphore = api_semaphore or asyncio.Semaphore(2)

    async def process_chunk(
        self,
        session_id: int,
        chunk_index: int,
        chunk_data: Dict[str, Any],
        pdf_id: int,
        cat_map: Dict[str, int]
    ) -> Dict[str, Any]:
        """Process a single chunk using ReAct pattern.
        
        Returns dict with: success, questions_count, summary, error
        """
        db = SessionLocal()
        react_steps = []
        chunk_label = chunk_data.get("label", f"chunk {chunk_index+1}")
        chunk_text = chunk_data.get("text", "")

        try:
            # === Thought 1: Analyze chunk ===
            thought_1 = (
                f"开始处理 {chunk_label}。"
                f"文本长度={len(chunk_text)}字符。"
                f"前100字: {chunk_text[:100]}"
            )
            self.memory.add_message(session_id, "thought", thought_1)
            react_steps.append({"step": "thought_1", "content": thought_1})

            # Check if text is empty or OCR failed
            if not chunk_text.strip() or "[OCR failed]" in chunk_text:
                obs = "文本为空或OCR失败，跳过此chunk"
                self.memory.add_message(session_id, "observation", obs)
                react_steps.append({"step": "observation_1", "content": obs})
                return {"success": True, "questions_count": 0, "summary": obs, "error": ""}

            # === Action 1: Call GLM API ===
            action_1 = f"调用GLM-5.2提取题目 (max_tokens=32000)"
            self.memory.add_message(session_id, "action", action_1)
            react_steps.append({"step": "action_1", "content": action_1})

            questions = []
            try:
                async with self._api_semaphore:
                    questions = await self.kimi.extract_questions(chunk_text)
                obs_1 = f"GLM返回 {len(questions)} 道题"
                self.memory.add_message(session_id, "observation", obs_1)
                react_steps.append({"step": "observation_1", "content": obs_1})
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                obs_1 = f"GLM调用失败: {err}"
                self.memory.add_message(session_id, "observation", obs_1)
                react_steps.append({"step": "observation_1", "content": obs_1, "error": err})

                # === Thought 2: Decide retry strategy ===
                thought_2 = f"第一次失败({err})。检查是否值得重试。"
                self.memory.add_message(session_id, "thought", thought_2)
                react_steps.append({"step": "thought_2", "content": thought_2})

                # Check if text has question markers (worth retrying)
                has_markers = any(m in chunk_text for m in [
                    "选择题", "正确的是", "错误的是", "不属于", "属于", "是指",
                    "特点是", "配伍", "共用备选", "综合分析", "多项选择"
                ])

                if not has_markers:
                    obs_2 = "文本无题目标记，标记为完成(0题)"
                    self.memory.add_message(session_id, "observation", obs_2)
                    react_steps.append({"step": "observation_2", "content": obs_2})
                    return {"success": True, "questions_count": 0, "summary": obs_2, "error": ""}

                # === Action 2: Retry ===
                action_2 = "重试GLM调用"
                self.memory.add_message(session_id, "action", action_2)
                react_steps.append({"step": "action_2", "content": action_2})

                try:
                    async with self._api_semaphore:
                        questions = await self.kimi.extract_questions(chunk_text)
                    obs_2 = f"重试成功，返回 {len(questions)} 道题"
                except Exception as e2:
                    err2 = f"{type(e2).__name__}: {e2}"
                    obs_2 = f"重试也失败: {err2}"
                    self.memory.add_message(session_id, "observation", obs_2)
                    react_steps.append({"step": "observation_2", "content": obs_2, "error": err2})
                    return {"success": False, "questions_count": 0, "summary": obs_2, "error": err2}

                self.memory.add_message(session_id, "observation", obs_2)
                react_steps.append({"step": "observation_2", "content": obs_2})

            # === Observation: Validate and save questions ===
            if questions:
                saved = 0
                for q in questions:
                    existing = db.query(Question).filter(
                        Question.pdf_id == pdf_id,
                        Question.question_text == q["question_text"]
                    ).first()
                    if existing:
                        continue

                    category_id = _match_category_for_chunk(
                        db, pdf_id, chunk_data.get("start_page", 1), cat_map
                    )

                    question = Question(
                        pdf_id=pdf_id,
                        category_id=category_id,
                        question_text=q["question_text"],
                        options=q.get("options", []),
                        answer=str(q.get("answer", "")),
                        explanation=q.get("explanation", ""),
                        question_type=q.get("question_type", "single"),
                        difficulty=min(5, max(1, q.get("difficulty", 3))),
                        question_number=str(q.get("question_number", "")),
                        chapter=q.get("chapter", ""),
                        section=q.get("section", ""),
                        page_number=chunk_data.get("start_page", 0)
                    )
                    db.add(question)
                    saved += 1

                db.commit()
                obs_final = f"保存了 {saved}/{len(questions)} 道题到数据库"
            else:
                obs_final = "没有提取到题目"

            self.memory.add_message(session_id, "observation", obs_final)
            react_steps.append({"step": "observation_final", "content": obs_final})

            return {
                "success": True,
                "questions_count": len(questions),
                "summary": obs_final,
                "error": "",
                "react_steps": react_steps
            }

        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            tb = traceback.format_exc()[:500]
            self.memory.add_message(session_id, "observation", f"异常: {err}\n{tb}")
            return {"success": False, "questions_count": 0, "summary": err, "error": err}
        finally:
            db.close()


def _match_category_for_chunk(db: Session, pdf_id: int, page_number: int, cat_map: Dict) -> Optional[int]:
    """Match a question to a category based on page number."""
    if not cat_map:
        return None
    categories = db.query(Category).filter(Category.pdf_id == pdf_id).order_by(Category.order_index).all()
    if not categories:
        return list(cat_map.values())[0] if cat_map else None
    pdf = db.query(PDFFile).filter(PDFFile.id == pdf_id).first()
    if not pdf or pdf.total_pages == 0:
        return categories[0].id
    pages_per_cat = max(1, pdf.total_pages // len(categories))
    cat_idx = min(page_number // pages_per_cat, len(categories) - 1)
    return categories[cat_idx].id


class TaskCoordinator:
    """Coordinates multi-agent parallel parsing.
    
    - Creates an AgentSession in DB
    - Creates TaskState rows for each chunk
    - Spawns N worker agents in parallel
    - Each worker pulls pending tasks from the queue
    - Breakpoint resume: re-run skips 'done' tasks, retries 'failed' ones
    """

    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self.kimi = KimiService()

    def run_parse(
        self,
        pdf_id: int,
        chunks: List[Dict[str, Any]],
        cat_map: Dict[str, int],
        task_type: str = "parse_questions"
    ) -> Dict[str, Any]:
        """Run parallel parsing with multiple agents.
        
        Args:
            pdf_id: PDF file ID
            chunks: list of {text, start_page, end_page, label}
            cat_map: category mapping
            task_type: task type
            
        Returns:
            dict with session_id, total_questions, status, etc.
        """
        db = SessionLocal()
        try:
            # === Create or resume session ===
            session = db.query(AgentSession).filter(
                AgentSession.pdf_id == pdf_id,
                AgentSession.task_type == task_type,
                AgentSession.status.in_(["running", "paused"])
            ).first()

            if session:
                print(f"[Coordinator] Resuming session {session.id} "
                      f"({session.done_chunks}/{session.total_chunks} done)", flush=True)
                session.status = "running"
            else:
                session = AgentSession(
                    pdf_id=pdf_id,
                    task_type=task_type,
                    status="running",
                    total_chunks=len(chunks),
                    done_chunks=0,
                    failed_chunks=0,
                    total_tokens_used=0,
                    memory_compressed_count=0
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                print(f"[Coordinator] Created new session {session.id} "
                      f"with {len(chunks)} chunks", flush=True)

            # === Create TaskState rows for new chunks ===
            existing_tasks = db.query(TaskState).filter(
                TaskState.session_id == session.id
            ).all()
            existing_indices = {t.chunk_index for t in existing_tasks}

            for i, chunk in enumerate(chunks):
                if i not in existing_indices:
                    task = TaskState(
                        session_id=session.id,
                        chunk_index=i,
                        chunk_label=chunk.get("label", f"chunk {i+1}/{len(chunks)}"),
                        status="pending",
                        retry_count=0,
                        max_retries=3,
                        react_steps=[]
                    )
                    db.add(task)
            db.commit()

            # === Get pending/failed tasks ===
            pending_tasks = db.query(TaskState).filter(
                TaskState.session_id == session.id,
                TaskState.status.in_(["pending", "failed"])
            ).order_by(TaskState.chunk_index).all()

            print(f"[Coordinator] {len(pending_tasks)} tasks to process "
                  f"with {self.num_workers} workers", flush=True)

            # === Run parallel workers ===
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._run_workers(session.id, pending_tasks, chunks, pdf_id, cat_map)
                )
            finally:
                loop.close()

            # === Update session status ===
            db.refresh(session)
            total_questions = db.query(Question).filter(Question.pdf_id == pdf_id).count()
            done_count = db.query(TaskState).filter(
                TaskState.session_id == session.id,
                TaskState.status == "done"
            ).count()
            failed_count = db.query(TaskState).filter(
                TaskState.session_id == session.id,
                TaskState.status == "failed"
            ).count()

            session.done_chunks = done_count
            session.failed_chunks = failed_count

            if failed_count == 0 and done_count == session.total_chunks:
                session.status = "completed"
            elif done_count > 0:
                session.status = "paused"  # partial completion
            else:
                session.status = "failed"

            session.result_summary = f"Extracted {total_questions} questions from {done_count}/{session.total_chunks} chunks"
            session.completed_at = datetime.utcnow()
            db.commit()

            return {
                "session_id": session.id,
                "status": session.status,
                "total_chunks": session.total_chunks,
                "done_chunks": done_count,
                "failed_chunks": failed_count,
                "total_questions": total_questions,
                "memory_compressed": session.memory_compressed_count,
                "total_tokens": session.total_tokens_used
            }

        finally:
            db.close()

    async def _run_workers(
        self,
        session_id: int,
        pending_tasks: List[TaskState],
        chunks: List[Dict],
        pdf_id: int,
        cat_map: Dict[str, int]
    ) -> None:
        """Run multiple agent workers in parallel."""
        db = SessionLocal()
        memory = MemoryManager(db, self.kimi)
        
        # Allow up to 2 concurrent GLM API calls
        api_semaphore = asyncio.Semaphore(min(2, self.num_workers))
        
        # Build task queue (chunk_index -> chunk_data)
        chunk_map = {i: chunks[i] for i in range(len(chunks))}
        
        # Create a queue of chunk indices to process
        task_queue = asyncio.Queue()
        for task in pending_tasks:
            await task_queue.put(task.chunk_index)

        # Progress tracking
        total = len(pending_tasks)
        completed = 0

        async def worker(worker_id: str):
            nonlocal completed
            agent = AgentWorker(worker_id, self.kimi, memory, api_semaphore)

            while True:
                try:
                    chunk_idx = task_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                # Mark task as running
                db_task = db.query(TaskState).filter(
                    TaskState.session_id == session_id,
                    TaskState.chunk_index == chunk_idx
                ).first()
                if db_task:
                    db_task.status = "running"
                    db_task.worker_id = worker_id
                    db_task.started_at = datetime.utcnow()
                    db.commit()

                chunk_data = chunk_map.get(chunk_idx, {})
                label = db_task.chunk_label if db_task else f"chunk {chunk_idx+1}"
                chunk_data["label"] = label

                print(f"  [{worker_id}] Processing {label}...", flush=True)

                result = await agent.process_chunk(
                    session_id, chunk_idx, chunk_data, pdf_id, cat_map
                )

                # Update task state
                if db_task:
                    db_task.status = "done" if result["success"] else "failed"
                    db_task.questions_extracted = result.get("questions_count", 0)
                    db_task.result_summary = result.get("summary", "")
                    db_task.error_message = result.get("error", "")
                    db_task.react_steps = result.get("react_steps", [])
                    db_task.completed_at = datetime.utcnow()
                    db.commit()

                completed += 1
                print(f"  [{worker_id}] Done {label}: "
                      f"{result.get('questions_count', 0)} questions "
                      f"({completed}/{total})", flush=True)

        # Launch workers
        workers = [asyncio.create_task(worker(f"worker-{i}")) for i in range(self.num_workers)]
        await asyncio.gather(*workers)
        
        db.close()
