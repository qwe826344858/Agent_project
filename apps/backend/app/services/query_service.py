"""搜索词生成服务 —— 根据用户问题和意图生成结构化搜索关键词"""

import logging
from datetime import datetime

from app.core.errors import UpstreamError, UpstreamTimeoutError
from app.schemas.chat import QueryResult

# ---------- 依赖导入（兼容尚未实现的模块） ----------

try:
    from app.services.llm_client import llm_client
except ImportError:
    llm_client = None  # type: ignore[assignment]

try:
    from app.services.prompts import QUERY_SYSTEM_PROMPT, build_query_user_prompt
except ImportError:
    # 如果 prompts 模块还没准备好，使用内置 fallback 常量
    QUERY_SYSTEM_PROMPT = (
        "你是一名保险领域搜索关键词生成助手。根据用户的问题和识别出的意图，"
        "生成 3-5 个精准的中文搜索关键词，用于在知识库或搜索引擎中检索相关内容。\n"
        "要求：\n"
        "1. 每个关键词必须包含问题中的核心实体（如产品名、险种、条款名等）。\n"
        "2. 关键词应覆盖不同搜索角度以提升召回率。\n"
        "3. 对于推荐类问题，加入当前年份以提升时效性。"
    )

    def build_query_user_prompt(message: str, intent: str) -> str:  # type: ignore[misc]
        current_year = datetime.now().year
        return (
            f"用户问题：{message}\n"
            f"识别意图：{intent}\n"
            f"当前年份：{current_year}\n\n"
            f"请返回 JSON，包含字段：\n"
            f'- queries: 搜索关键词列表（3-5 个字符串）'
        )

logger = logging.getLogger(__name__)

# 需要附加年份的意图类型
_TIME_SENSITIVE_INTENTS = {"product_recommendation", "product_query"}


class QueryService:
    """搜索词生成服务"""

    async def generate(self, message: str, intent: str) -> list[str]:
        """
        根据用户问题和意图生成 3-5 个搜索关键词。

        参数：
            message: 用户原始问题
            intent: 意图分类字符串

        返回：
            关键词字符串列表
        """
        if llm_client is None:
            raise UpstreamError("llm_client 尚未初始化，无法生成搜索词")

        # 1. 构建对话 messages
        messages = [
            {"role": "system", "content": QUERY_SYSTEM_PROMPT},
            {"role": "user", "content": build_query_user_prompt(message, intent)},
        ]

        # 2. 调用 LLM，获取 JSON 结果
        try:
            json_result: dict = await llm_client.call_json(
                messages, temperature=0.3
            )
        except TimeoutError as exc:
            logger.error("搜索词生成 LLM 调用超时: %s", exc)
            raise UpstreamTimeoutError("搜索词生成服务超时") from exc
        except Exception as exc:
            logger.error("搜索词生成 LLM 调用失败: %s", exc)
            raise UpstreamError("搜索词生成服务异常") from exc

        # 3. 解析为 QueryResult
        result = QueryResult(**json_result)
        queries = result.queries

        # 4. 对时效性敏感的意图，确保关键词包含当前年份
        if intent in _TIME_SENSITIVE_INTENTS:
            queries = self._inject_year(queries)

        # 5. 限制返回 3-5 个关键词
        queries = queries[:5]

        logger.info("搜索词生成完成 intent=%s queries=%s", intent, queries)
        return queries

    # ------------------------------------------------------------------
    @staticmethod
    def _inject_year(queries: list[str]) -> list[str]:
        """为关键词列表注入当前年份，提升时效性"""
        current_year = str(datetime.now().year)
        enriched: list[str] = []
        year_added = False
        for q in queries:
            if current_year in q:
                year_added = True
            enriched.append(q)
        # 如果没有任何关键词包含年份，给第一个关键词追加年份
        if not year_added and enriched:
            enriched[0] = f"{enriched[0]} {current_year}"
        return enriched


# 导出全局单例
query_service = QueryService()
