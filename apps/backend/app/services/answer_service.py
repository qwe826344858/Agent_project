"""回答生成服务 — 基于搜索结果生成结构化回答"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.schemas.chat import AnswerResult, SearchResultItem

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 导入 LLM 客户端（不存在时使用 stub）
# ------------------------------------------------------------------
try:
    from app.services.llm_client import llm_client  # type: ignore[import-untyped]
except ImportError:
    logger.warning("llm_client 模块不可用，使用 stub 占位")

    class _LLMClientStub:
        """LLM 客户端 stub — 在 llm_client 模块就绪前提供占位实现。"""

        async def call_text(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
            return json.dumps(
                {"summary": "暂无法生成回答（LLM 服务未就绪）", "details": [], "caution": None},
                ensure_ascii=False,
            )

        async def call_text_stream(
            self, messages: list[dict[str, str]], **kwargs: Any
        ) -> AsyncGenerator[str, None]:
            yield "暂无法生成回答（LLM 服务未就绪）"

    llm_client = _LLMClientStub()  # type: ignore[assignment]

# ------------------------------------------------------------------
# 导入 Prompt 模板（不存在时使用 fallback）
# ------------------------------------------------------------------
try:
    from app.services.prompts import (  # type: ignore[import-untyped]
        ANSWER_SYSTEM_PROMPT,
        ANSWER_USER_TEMPLATE,
        FOLLOWUP_SYSTEM_PROMPT,
        FOLLOWUP_USER_TEMPLATE,
    )
except ImportError:
    logger.warning("prompts 模块不可用，使用内置 fallback 模板")

    ANSWER_SYSTEM_PROMPT: str = (  # type: ignore[no-redef]
        "你是一位专业的保险顾问 AI 助手。"
        "请根据提供的搜索资料，用通俗易懂的中文回答用户关于保险的问题。\n"
        "要求：\n"
        "1. 回答必须基于提供的参考资料，不要编造信息。\n"
        "2. 如果资料不足以完整回答，请如实说明。\n"
        "3. 输出 JSON 格式：{\"summary\": \"...\", \"details\": [\"...\", ...], \"caution\": \"...或null\"}\n"
        "4. summary 为一句话总结；details 为分点说明；caution 为风险提示（无则为 null）。"
    )

    ANSWER_USER_TEMPLATE: str = (  # type: ignore[no-redef]
        "## 用户问题\n{message}\n\n"
        "## 识别意图\n{intent}\n\n"
        "## 参考资料\n{search_context}\n\n"
        "请根据以上资料回答用户问题，以 JSON 格式输出。"
    )

    FOLLOWUP_SYSTEM_PROMPT: str = (  # type: ignore[no-redef]
        "你是一位专业的保险顾问 AI 助手。"
        "用户的问题缺少一些关键信息，请生成自然、友好的追问话术，"
        "引导用户补充缺失信息。"
    )

    FOLLOWUP_USER_TEMPLATE: str = (  # type: ignore[no-redef]
        "用户说：{message}\n\n"
        "缺失的信息项：{missing_slots}\n\n"
        "请生成一段自然的追问话术（纯文本，不要 JSON）。"
    )


class AnswerService:
    """回答生成服务 — 结合搜索结果与 LLM 生成结构化回答"""

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    async def generate(
        self,
        message: str,
        intent: str,
        search_results: list[SearchResultItem],
    ) -> AnswerResult:
        """
        基于用户问题和搜索结果生成结构化回答。

        流程：
        1. 将搜索结果格式化为上下文摘要
        2. 构建 messages 并调用 LLM
        3. 解析 LLM 输出为 AnswerResult
        """
        search_context = self._format_search_context(search_results)
        messages = self._build_answer_messages(message, intent, search_context)

        raw = await llm_client.call_text(messages)
        return self._parse_answer(raw)

    async def generate_stream(
        self,
        message: str,
        intent: str,
        search_results: list[SearchResultItem],
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回答，逐块 yield 文本。

        适用于 SSE 场景，直接将 LLM 返回的文本块透传给客户端。
        """
        search_context = self._format_search_context(search_results)
        messages = self._build_answer_messages(message, intent, search_context)

        async for chunk in llm_client.call_text_stream(messages):
            yield chunk

    async def generate_followup(
        self, message: str, missing_slots: list[str]
    ) -> str:
        """
        生成追问话术，引导用户补充缺失信息。
        """
        messages = self._build_followup_messages(message, missing_slots)
        return await llm_client.call_text(messages)

    # ------------------------------------------------------------------
    # 内部方法：构建消息
    # ------------------------------------------------------------------

    def _build_answer_messages(
        self, message: str, intent: str, search_context: str
    ) -> list[dict[str, str]]:
        """构建回答生成的 LLM 消息列表。"""
        user_content = ANSWER_USER_TEMPLATE.format(
            message=message,
            intent=intent,
            search_context=search_context,
        )
        return [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    def _build_followup_messages(
        self, message: str, missing_slots: list[str]
    ) -> list[dict[str, str]]:
        """构建追问话术的 LLM 消息列表。"""
        slots_text = "、".join(missing_slots) if missing_slots else "（无）"
        user_content = FOLLOWUP_USER_TEMPLATE.format(
            message=message,
            missing_slots=slots_text,
        )
        return [
            {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    # ------------------------------------------------------------------
    # 内部方法：格式化搜索上下文
    # ------------------------------------------------------------------

    @staticmethod
    def _format_search_context(results: list[SearchResultItem]) -> str:
        """
        将搜索结果格式化为上下文摘要。

        格式包含来源网站和 URL，便于 LLM 提取产品信息和链接。
        """
        if not results:
            return "（无搜索结果）"

        parts: list[str] = []
        for idx, item in enumerate(results, start=1):
            parts.append(
                f"[{idx}] {item.title}\n"
                f"网站: {item.site}\n"
                f"链接: {item.url}\n"
                f"摘要: {item.snippet}"
            )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # 内部方法：解析 LLM 输出
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_answer(raw: str) -> AnswerResult:
        """
        将 LLM 的文本输出解析为 AnswerResult。

        支持：
        - 标准 JSON 输出
        - 包含 markdown 代码块的 JSON
        - 纯文本（降级为 summary）
        """
        text = raw.strip()

        # 尝试去除 markdown 代码块标记
        if text.startswith("```"):
            # 去掉首行 (```json 或 ```) 和末行 (```)
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # 尝试 JSON 解析
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return AnswerResult(
                    summary=data.get("summary", ""),
                    details=data.get("details", []),
                    caution=data.get("caution"),
                )
        except (json.JSONDecodeError, TypeError):
            pass

        # 降级：把整段文本作为 summary
        logger.warning("LLM 输出非有效 JSON，降级为纯文本摘要")
        return AnswerResult(summary=text, details=[], caution=None)


# 全局单例
answer_service = AnswerService()
