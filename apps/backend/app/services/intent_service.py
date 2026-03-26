"""意图识别服务 —— 解析用户问题的意图类型并判断是否需要追问"""

import logging
from datetime import datetime

from app.core.errors import UpstreamError, UpstreamTimeoutError
from app.schemas.chat import IntentResult

# ---------- 依赖导入（兼容尚未实现的模块） ----------

try:
    from app.services.llm_client import llm_client
except ImportError:
    llm_client = None  # type: ignore[assignment]

try:
    from app.services.prompts import INTENT_SYSTEM_PROMPT, build_intent_user_prompt
except ImportError:
    # 如果 prompts 模块还没准备好，使用内置 fallback 常量
    INTENT_SYSTEM_PROMPT = (
        "你是一名保险领域的意图识别助手。根据用户的问题，输出 JSON 格式的意图分类结果。\n"
        "可选意图：knowledge_explain, product_query, product_recommendation, "
        "clause_explain, comparison, underwriting_basic, out_of_scope。\n"
        "同时判断是否需要向用户追问以补全缺失信息。"
    )

    def build_intent_user_prompt(message: str) -> str:  # type: ignore[misc]
        return (
            f"请分析以下用户问题的意图，返回 JSON，包含字段：\n"
            f"- intent: 意图类型\n"
            f"- needs_followup: 是否需要追问 (boolean)\n"
            f"- missing_slots: 缺失的槽位列表\n"
            f"- reason: 判断理由\n\n"
            f"用户问题：{message}"
        )

logger = logging.getLogger(__name__)

# ---------- 追问触发规则 ----------

# 各意图下的关键槽位和触发追问的最低缺失数
# min_missing: 缺失槽位数 >= 此值才触发追问
_FOLLOWUP_RULES: dict[str, dict] = {
    "product_recommendation": {
        "slots": ["age", "budget", "preference"],
        "min_missing": 2,  # 已提供年龄+偏好但缺预算时不追问，直接推荐
    },
    "comparison": {
        "slots": ["product_names"],
        "min_missing": 1,
    },
    "clause_explain": {
        "slots": ["product_name", "clause_target"],
        "min_missing": 1,
    },
}


class IntentService:
    """意图识别服务"""

    async def classify(self, message: str) -> IntentResult:
        """
        识别用户问题的意图类型和是否需要追问。

        返回 IntentResult：
        - intent: 意图枚举
        - needs_followup: 是否需要追问
        - missing_slots: 缺失的槽位
        - reason: 判断理由
        """
        if llm_client is None:
            raise UpstreamError("llm_client 尚未初始化，无法进行意图识别")

        # 1. 构建对话 messages
        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": build_intent_user_prompt(message)},
        ]

        # 2. 调用 LLM，获取 JSON 结果
        try:
            json_result: dict = await llm_client.call_json(
                messages, temperature=0.2
            )
        except TimeoutError as exc:
            logger.error("意图识别 LLM 调用超时: %s", exc)
            raise UpstreamTimeoutError("意图识别服务超时") from exc
        except Exception as exc:
            logger.error("意图识别 LLM 调用失败: %s", exc)
            raise UpstreamError("意图识别服务异常") from exc

        # 3. 解析为 IntentResult
        result = IntentResult(**json_result)

        # 4. 根据追问规则修正 needs_followup 和 missing_slots
        result = self._apply_followup_rules(result)

        logger.info(
            "意图识别完成 intent=%s needs_followup=%s missing_slots=%s",
            result.intent,
            result.needs_followup,
            result.missing_slots,
        )
        return result

    # ------------------------------------------------------------------
    def _apply_followup_rules(self, result: IntentResult) -> IntentResult:
        """根据预定义规则判断是否需要追问并补全缺失槽位

        只有当缺失的关键槽位数量 >= min_missing 时才触发追问。
        例如：推荐意图下，用户已提供年龄+偏好但缺预算，缺失数=1 < min_missing=2，不追问。
        """
        rule = _FOLLOWUP_RULES.get(result.intent)
        if rule is None:
            return result

        required_slots = set(rule["slots"])
        min_missing = rule["min_missing"]

        # LLM 认为缺失的槽位与规则槽位取交集
        llm_missing = set(result.missing_slots)
        actual_missing = sorted(llm_missing & required_slots)

        if len(actual_missing) >= min_missing:
            result.needs_followup = True
            result.missing_slots = actual_missing
        else:
            # 缺失数不够，不追问，直接走搜索
            result.needs_followup = False
            result.missing_slots = actual_missing

        return result


# 导出全局单例
intent_service = IntentService()
