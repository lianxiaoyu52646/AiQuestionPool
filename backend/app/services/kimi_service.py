# -*- coding: utf-8 -*-
"""AI API service - question & answer extraction (GLM-5.2)"""
import httpx
import json
import re
from typing import List, Dict, Any
from app.config import get_settings

settings = get_settings()

# === Prompts ===

QUESTION_SYSTEM_PROMPT = """你是一个专业的题库解析助手。你的任务是从PDF文本中提取结构化题目。

请严格按照以下JSON格式输出题目列表：
[
  {
    "question_number": "1",
    "chapter": "第一章执业药师与中药药学服务",
    "section": "第一节 中药药学服务及其模式",
    "question_text": "题干内容",
    "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
    "answer": "",
    "explanation": "",
    "question_type": "single",
    "difficulty": 3
  }
]

规则：
1. question_number: 题目在当前"节+题型"范围内的编号，如 "1", "2", "15"。配伍题组内每小题各自编号
2. chapter: 章节标题，如 "第一章执业药师与中药药学服务"（去掉空格）
3. section: 节标题，如 "第一节 中药药学服务及其模式"（去掉空格）。如果没有节，留空
4. question_type: 必须是以下之一（与答案PDF对齐）：
   - "single" 单项选择题
   - "multiple" 多项选择题
   - "matching" 配伍选择题（一组共用题干，每小题单独作答）
   - "comprehensive" 综合分析题（共用案例材料的大题）
   - "judge" 判断题
   - "fill" 填空题
5. difficulty: 1-5, 1最简单, 5最难
6. answer: 题目PDF通常没有答案，留空字符串 ""
7. explanation: 题目PDF通常没有解析，留空字符串 ""
8. 保持题干原文，不要修改
9. 每道题必须包含完整选项（如有）
10. 注意：配伍选择题要识别"以下共用备选项"等提示，每小题分别输出一条记录，question_number 为小题号
"""

ANSWER_SYSTEM_PROMPT = """你是一个专业的答案解析提取助手。你的任务是从答案PDF文本中提取每道题的答案和解析。

请严格按照以下JSON格式输出：
[
  {
    "question_number": "1",
    "chapter": "第一章执业药师与中药药学服务",
    "section": "第一节 中药药学服务及其模式",
    "answer": "C",
    "explanation": "本题考查中药药学服务的模式与内容..."
  }
]

规则：
1. question_number: 题目在当前章节内的编号，必须与题目PDF中的编号一致
2. chapter: 章节标题，必须与题目PDF中的章节标题一致
3. section: 节标题，必须与题目PDF中的节标题一致。如果没有节，留空
4. answer: 题目答案，如 "A", "AB", "True", "False"
5. explanation: 答案解析内容，保持原文
6. 注意：答案PDF中通常有 "答案：X" 的格式，请准确提取
"""

COMBINED_SYSTEM_PROMPT = """你是一个专业的题库解析助手。你的任务是从PDF文本中提取结构化题目（含答案）。

请严格按照以下JSON格式输出题目列表：
[
  {
    "question_number": "1",
    "chapter": "第一章执业药师与中药药学服务",
    "section": "第一节 中药药学服务及其模式",
    "question_text": "题干内容",
    "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
    "answer": "A",
    "explanation": "答案解析",
    "question_type": "single",
    "difficulty": 3
  }
]

规则：
1. question_number: 题目在当前章节内的编号
2. chapter: 章节标题
3. section: 节标题，如果没有节留空
4. question_type: single / multiple / judge / fill
5. difficulty: 1-5
6. answer: 题目答案
7. explanation: 答案解析
8. 保持原文，不要修改
"""


class KimiService:
    """AI API service (GLM-5.2)"""

    def __init__(self):
        self.api_key = settings.upstream_api_key
        self.base_url = settings.upstream_base_url.rstrip("/")
        self.model = settings.model_name
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(600.0, connect=30.0),
            verify=False
        )

    async def _call_api_async(self, system_prompt: str, user_prompt: str, max_tokens: int = 32000) -> str:
        """Call AI API and return raw content string.

        GLM-5.2 is a reasoning model: it first generates a `reasoning` chain-of-thought,
        then produces the final answer in `content`. If max_tokens is too low, the
        reasoning phase exhausts the budget and `content` stays null.
        When content is None, we retry with doubled max_tokens.
        GLM-5.2 max_model_len = 558,752 tokens.

        On ReadTimeout, retries with exponential backoff (30s, 60s, 120s).
        """
        import asyncio as _aio

        for attempt in range(3):
            token_budget = max_tokens * (2 ** attempt)
            try:
                response = await self.client.post(
                    "/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": token_budget
                    }
                )
            except httpx.ReadTimeout:
                wait = 30 * (2 ** attempt)
                print(f"    [API ERROR] ReadTimeout (attempt {attempt+1}/3), "
                      f"waiting {wait}s before retry...", flush=True)
                await _aio.sleep(wait)
                continue
            except httpx.ConnectTimeout:
                wait = 15 * (2 ** attempt)
                print(f"    [API ERROR] ConnectTimeout (attempt {attempt+1}/3), "
                      f"waiting {wait}s before retry...", flush=True)
                await _aio.sleep(wait)
                continue
            except Exception as e:
                print(f"    [API ERROR] {type(e).__name__}: {e}", flush=True)
                raise
            print(f"    [API] status={response.status_code} (attempt {attempt+1}, max_tokens={token_budget})", flush=True)
            if response.status_code != 200:
                print(f"    [API] body={response.text[:500]}", flush=True)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content")
            if content:
                print(f"    [API] got content ({len(content)} chars)", flush=True)
                return content
            # content is None: reasoning phase exhausted token budget
            reasoning = message.get("reasoning") or ""
            print(f"    [API] content was None (reasoning={len(reasoning)} chars), retrying with more tokens", flush=True)
        # All retries exhausted - return reasoning as last resort
        print(f"    [API] all retries exhausted, using reasoning text", flush=True)
        return reasoning

    def _clean_json(self, content: str) -> str:
        """Clean markdown code blocks from API response"""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    def _parse_json_robust(self, content: str) -> list:
        """Parse JSON that may have unescaped quotes inside string values.
        
        GLM-5.2 sometimes produces JSON like:
        "question_text": "关于"以药品为中心"的说法"
        where the inner quotes are not escaped. This method uses a regex-based
        approach to extract key-value pairs and fix common issues.
        """
        # First try standard json.loads
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to fix unescaped quotes inside string values
        # Strategy: parse character by character, tracking string context
        fixed = self._fix_unescaped_quotes(content)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            print(f"    [JSON] still failed after fix: {e}", flush=True)
            print(f"    [JSON] fixed[:500]={fixed[:500]}", flush=True)
            # Last resort: try to extract individual JSON objects
            return self._extract_json_objects(content)

    def _fix_unescaped_quotes(self, text: str) -> str:
        """Fix unescaped double quotes inside JSON string values."""
        result = []
        i = 0
        in_string = False
        while i < len(text):
            ch = text[i]
            if not in_string:
                result.append(ch)
                if ch == '"':
                    in_string = True
            else:
                if ch == '\\':
                    # Escape sequence - copy as-is
                    result.append(ch)
                    if i + 1 < len(text):
                        result.append(text[i + 1])
                        i += 1
                elif ch == '"':
                    # Check if this quote ends the string or is an unescaped inner quote
                    # Look ahead to see if the next non-whitespace char is a JSON structural char
                    j = i + 1
                    while j < len(text) and text[j] in ' \t\r\n':
                        j += 1
                    if j < len(text) and text[j] in ':,}]':
                        # This quote ends the string
                        result.append(ch)
                        in_string = False
                    else:
                        # This is an unescaped inner quote - escape it
                        result.append('\\"')
                else:
                    result.append(ch)
            i += 1
        return ''.join(result)

    def _extract_json_objects(self, content: str) -> list:
        """Extract individual JSON objects from content that can't be parsed as a whole."""
        results = []
        depth = 0
        start = -1
        in_string = False
        escape = False
        for i, ch in enumerate(content):
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    obj_str = content[start:i + 1]
                    fixed = self._fix_unescaped_quotes(obj_str)
                    try:
                        obj = json.loads(fixed)
                        results.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start = -1
        return results

    async def extract_questions(self, text: str, category_hint: str = "") -> List[Dict[str, Any]]:
        """Extract questions from question PDF text (answer may be empty).
        
        Raises Exception on API/parse failures so caller can retry.
        Returns empty list only if text genuinely has no questions.
        """
        prompt = f"""请从以下PDF文本中提取所有题目，按JSON格式返回。

{'分类提示: ' + category_hint if category_hint else ''}

PDF文本内容：
{text[:12000]}

请只返回JSON格式的题目数组，不要添加其他说明。"""

        content = await self._call_api_async(QUESTION_SYSTEM_PROMPT, prompt)
        content = self._clean_json(content)
        questions = self._parse_json_robust(content)

        validated = []
        for q in questions:
            if "question_text" not in q:
                continue
            validated.append({
                "question_text": q.get("question_text", ""),
                "options": q.get("options", []),
                "answer": str(q.get("answer", "")),
                "explanation": q.get("explanation", ""),
                "question_type": q.get("question_type", "single"),
                "difficulty": min(5, max(1, q.get("difficulty", 3))),
                "question_number": str(q.get("question_number", "")),
                "chapter": q.get("chapter", ""),
                "section": q.get("section", "")
            })

        return validated

    async def extract_answers(self, text: str) -> List[Dict[str, Any]]:
        """Extract answers and explanations from answer PDF text"""
        prompt = f"""请从以下答案PDF文本中提取所有题目的答案和解析，按JSON格式返回。

PDF文本内容：
{text[:12000]}

请只返回JSON格式的数组，不要添加其他说明。"""

        try:
            content = await self._call_api_async(ANSWER_SYSTEM_PROMPT, prompt)
            content = self._clean_json(content)
            answers = json.loads(content)

            validated = []
            for a in answers:
                if "answer" not in a:
                    continue
                validated.append({
                    "question_number": str(a.get("question_number", "")),
                    "chapter": a.get("chapter", ""),
                    "section": a.get("section", ""),
                    "answer": str(a.get("answer", "")),
                    "explanation": a.get("explanation", "")
                })

            return validated

        except httpx.HTTPError as e:
            print(f"AI API request failed: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}, content: {content[:500]}")
            return []
        except Exception as e:
            print(f"Answer extraction failed: {e}")
            return []

    async def extract_combined(self, text: str, category_hint: str = "") -> List[Dict[str, Any]]:
        """Extract questions with answers from combined PDF (legacy mode)"""
        prompt = f"""请从以下PDF文本中提取所有题目（含答案），按JSON格式返回。

{'分类提示: ' + category_hint if category_hint else ''}

PDF文本内容：
{text[:12000]}

请只返回JSON格式的题目数组，不要添加其他说明。"""

        try:
            content = await self._call_api_async(COMBINED_SYSTEM_PROMPT, prompt)
            content = self._clean_json(content)
            questions = json.loads(content)

            validated = []
            for q in questions:
                if "question_text" not in q:
                    continue
                validated.append({
                    "question_text": q.get("question_text", ""),
                    "options": q.get("options", []),
                    "answer": str(q.get("answer", "")),
                    "explanation": q.get("explanation", ""),
                    "question_type": q.get("question_type", "single"),
                    "difficulty": min(5, max(1, q.get("difficulty", 3))),
                    "question_number": str(q.get("question_number", "")),
                    "chapter": q.get("chapter", ""),
                    "section": q.get("section", "")
                })

            return validated

        except httpx.HTTPError as e:
            print(f"AI API request failed: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}, content: {content[:500]}")
            return []
        except Exception as e:
            print(f"Combined extraction failed: {e}")
            return []

    async def extract_categories(self, text: str) -> List[Dict[str, str]]:
        """Extract chapter categories from PDF text"""
        prompt = f"""请分析以下PDF文本，提取章节分类结构。

请按以下JSON格式返回：
[
  {{"name": "第一章 执业药师与中药药学服务", "order_index": 1}},
  {{"name": "第二章 中医理论基础", "order_index": 2}}
]

PDF文本开头：
{text[:5000]}

只返回JSON，不要其他说明。"""

        try:
            content = await self._call_api_async(
                "你是一个文档结构分析助手，擅长提取章节标题。", prompt, max_tokens=4000
            )
            content = self._clean_json(content)
            if not content.startswith("["):
                content = content[content.find("["):content.rfind("]")+1]
            categories = json.loads(content)
            return categories

        except Exception as e:
            print(f"Category extraction failed: {e}")
            return []
