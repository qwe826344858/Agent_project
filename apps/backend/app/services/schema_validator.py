"""JSON Schema 校验器 —— 验证 LLM 输出是否符合预定义格式

LLM 返回的 JSON 可能存在字段缺失、类型错误等问题，
本模块对其进行校验并使用默认值兜底，确保下游逻辑安全消费。
"""

from __future__ import annotations

import logging

from app.schemas.chat import IntentResult, QueryResult

logger = logging.getLogger(__name__)

# 合法意图枚举值
_VALID_INTENTS: set[str] = {
    "knowledge_explain",
    "product_query",
    "product_recommendation",
    "clause_explain",
    "comparison",
    "underwriting_basic",
    "out_of_scope",
}


class SchemaValidator:
    """JSON Schema 校验器 — 验证 LLM 输出是否符合预定义格式"""

    @staticmethod
    def validate_intent(data: dict) -> IntentResult:
        """
        校验并返回 IntentResult。

        兜底规则：
        - intent 不在合法枚举中时默认为 "out_of_scope"
        - needs_followup 非布尔值或缺失时默认为 False
        - missing_slots 非列表时默认为空列表
        - reason 非字符串或缺失时默认为空字符串
        """
        if not isinstance(data, dict):
            logger.warning("validate_intent 收到非 dict 输入，使用全部默认值")
            data = {}

        # intent 校验：不在枚举中则回退到 out_of_scope
        intent = data.get("intent", "out_of_scope")
        if not isinstance(intent, str) or intent not in _VALID_INTENTS:
            logger.warning(
                "无效的 intent 值 '%s'，已回退为 'out_of_scope'", intent
            )
            intent = "out_of_scope"

        # needs_followup 校验：非布尔值时默认 False
        needs_followup = data.get("needs_followup", False)
        if not isinstance(needs_followup, bool):
            logger.warning(
                "needs_followup 类型错误（%s），已回退为 False",
                type(needs_followup).__name__,
            )
            needs_followup = False

        # missing_slots 校验：非列表时默认空列表，过滤非字符串元素
        missing_slots = data.get("missing_slots", [])
        if not isinstance(missing_slots, list):
            logger.warning(
                "missing_slots 类型错误（%s），已回退为空列表",
                type(missing_slots).__name__,
            )
            missing_slots = []
        else:
            missing_slots = [s for s in missing_slots if isinstance(s, str) and s]

        # reason 校验：非字符串时默认空字符串
        reason = data.get("reason", "")
        if not isinstance(reason, str):
            reason = ""

        return IntentResult(
            intent=intent,
            needs_followup=needs_followup,
            missing_slots=missing_slots,
            reason=reason,
        )

    @staticmethod
    def validate_query(data: dict) -> QueryResult:
        """
        校验并返回 QueryResult。

        兜底规则：
        - queries 非列表时转为空列表
        - 过滤空字符串和非字符串元素，确保列表中仅包含有效查询词
        """
        if not isinstance(data, dict):
            logger.warning("validate_query 收到非 dict 输入，使用全部默认值")
            data = {}

        queries = data.get("queries", [])

        # 非列表类型时回退为空列表
        if not isinstance(queries, list):
            logger.warning(
                "queries 类型错误（%s），已回退为空列表",
                type(queries).__name__,
            )
            queries = []
        else:
            # 过滤：仅保留非空字符串
            queries = [
                q.strip()
                for q in queries
                if isinstance(q, str) and q.strip()
            ]

        return QueryResult(queries=queries)


# 导出全局实例
schema_validator = SchemaValidator()
