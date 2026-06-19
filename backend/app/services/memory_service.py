# -*- coding: utf-8 -*-
"""Memory management service for agent sessions.

Implements the "compress oldest 30%" strategy:
- When a session's accumulated messages exceed a token threshold,
  the oldest 30% of active messages are sent to GLM for summarization.
- The summary replaces those messages (marked as compressed).
- This keeps the context window manageable for long-running tasks.

Inspired by Claude Code's context management approach.
"""
import json
import math
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import AgentSession, AgentMessage
from app.services.kimi_service import KimiService

# Token threshold: when accumulated active messages exceed this, trigger compression
TOKEN_THRESHOLD = 40000  # ~40K tokens before compression
COMPRESSION_RATIO = 0.3  # compress oldest 30% of active messages


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1.5 chars per token for Chinese, ~4 for English."""
    if not text:
        return 0
    # Simple heuristic: count Chinese chars as 1 token each, other chars as 0.25
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return chinese_chars + other_chars // 4


class MemoryManager:
    """Manages agent session memory with automatic compression."""

    def __init__(self, db: Session, kimi_service: KimiService):
        self.db = db
        self.kimi = kimi_service

    def add_message(self, session_id: int, role: str, content: str) -> AgentMessage:
        """Add a message to the session and check if compression is needed."""
        token_est = estimate_tokens(content)
        msg = AgentMessage(
            session_id=session_id,
            role=role,
            content=content,
            token_estimate=token_est,
            is_compressed=0
        )
        self.db.add(msg)
        
        session = self.db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if session:
            session.total_tokens_used = (session.total_tokens_used or 0) + token_est
        self.db.commit()
        
        # Check if compression is needed
        self._maybe_compress(session_id)
        
        return msg

    def get_active_messages(self, session_id: int) -> List[AgentMessage]:
        """Get all active (non-compressed) messages for a session."""
        return self.db.query(AgentMessage).filter(
            AgentMessage.session_id == session_id,
            AgentMessage.is_compressed == 0
        ).order_by(AgentMessage.created_at).all()

    def get_context_text(self, session_id: int) -> str:
        """Get the current context as text (active messages + latest summary)."""
        messages = self.get_active_messages(session_id)
        lines = []
        for msg in messages:
            prefix = f"[{msg.role}]"
            lines.append(f"{prefix} {msg.content}")
        return "\n".join(lines)

    def _maybe_compress(self, session_id: int) -> bool:
        """Check if compression is needed and perform it.
        
        Returns True if compression was performed.
        """
        active_msgs = self.get_active_messages(session_id)
        total_tokens = sum(m.token_estimate or 0 for m in active_msgs)
        
        if total_tokens <= TOKEN_THRESHOLD:
            return False
        
        # Need to compress oldest 30%
        compress_count = max(1, math.ceil(len(active_msgs) * COMPRESSION_RATIO))
        to_compress = active_msgs[:compress_count]
        
        print(f"  [Memory] Compressing {compress_count}/{len(active_msgs)} messages "
              f"({sum(m.token_estimate or 0 for m in to_compress)} tokens)", flush=True)
        
        # Build text to summarize
        history_text = "\n".join(
            f"[{m.role}] {m.content}" for m in to_compress
        )
        
        # Ask GLM to compress
        summary = self._compress_with_llm(history_text)
        
        # Mark old messages as compressed
        for msg in to_compress:
            msg.is_compressed = 1
        
        # Insert summary message
        summary_msg = AgentMessage(
            session_id=session_id,
            role="summary",
            content=f"[压缩记忆] 之前{compress_count}条操作的总结:\n{summary}",
            token_estimate=estimate_tokens(summary),
            is_compressed=0
        )
        self.db.add(summary_msg)
        
        session = self.db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if session:
            session.memory_compressed_count = (session.memory_compressed_count or 0) + 1
        
        self.db.commit()
        print(f"  [Memory] Compression done. Summary: {summary[:100]}...", flush=True)
        return True

    def _compress_with_llm(self, history_text: str) -> str:
        """Use GLM to compress history into a brief summary."""
        prompt = f"""请将以下Agent操作历史压缩成简洁的总结（几句话即可），保留关键信息：
- 处理了哪些chunk
- 每个chunk的结果（成功/失败，提取了多少题）
- 遇到的问题和解决方案

操作历史：
{history_text[:8000]}

请直接输出总结，不要其他说明。"""

        try:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                content = loop.run_until_complete(
                    self.kimi._call_api_async(
                        "你是一个记忆压缩助手。请简洁地总结操作历史。",
                        prompt,
                        max_tokens=2000
                    )
                )
            finally:
                loop.close()
            return content.strip()
        except Exception as e:
            # Fallback: simple truncation
            return f"[压缩失败，使用截断] {history_text[:500]}"
