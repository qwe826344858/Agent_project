"""聊天编排器 — 双通道并行架构

通道A（产品卡片）：ProductSearchService 搜索平台商品 → products 事件
通道B（文字建议）：通用搜索 + LLM 回答 → delta 事件
异步：价格抓取 → products_update 事件

当前为轻量函数编排实现（Orchestrator Impl: lite），
后续可通过 ORCHESTRATOR=langgraph 开关切换为 LangGraph 实现。
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from app.schemas.chat import (
    IntentResult,
    SearchResultItem,
    SourceItem,
)
from app.services.intent_service import intent_service
from app.services.query_service import query_service
from app.services.search_service import search_service
from app.services.answer_service import answer_service

# 平台直连 API（直接调用各保险平台的搜索接口，不依赖任何搜索引擎）
try:
    from app.services.platform_apis import search_all_platforms
    _PLATFORM_API_AVAILABLE = True
except ImportError:
    _PLATFORM_API_AVAILABLE = False

logger = logging.getLogger("smartinsure.orchestrator")

# 所有意图都直接用原始问题搜索，跳过搜索词生成 LLM 调用
# 这样可以节省 10-15 秒的 LLM 调用延迟，搜索质量由 SearchService 的策略保证
_DIRECT_SEARCH_INTENTS = {
    "knowledge_explain",
    "product_query",
    "product_recommendation",
    "clause_explain",
    "comparison",
    "underwriting_basic",
}

# 触发产品搜索的意图集合
_PRODUCT_SEARCH_INTENTS = {"product_recommendation", "product_query", "comparison"}


@dataclass
class ChatContext:
    """单次对话编排的上下文"""
    message: str
    request_id: str = ""
    intent: IntentResult | None = None
    queries: list[str] = field(default_factory=list)
    search_results: list[SearchResultItem] = field(default_factory=list)
    sources: list[SourceItem] = field(default_factory=list)
    products: list = field(default_factory=list)


class ChatOrchestrator:
    """聊天编排器 — 双通道并行协调各 Domain Service 完成一次完整问答

    通道A：产品卡片（ProductSearchService → products / products_update 事件）
    通道B：文字建议（通用搜索 + LLM → delta 事件）
    """

    async def run_stream(
        self, message: str, request_id: str = ""
    ) -> AsyncGenerator[dict, None]:
        """
        流式执行完整对话链路，yield SSE 事件字典。

        双通道流程：
        1. 意图识别
        2. 追问/超范围判断 → 直接返回
        3. 判断是否触发产品搜索
        4. 并行执行通道A（产品搜索）和通道B（通用搜索）
        5. 立即推送 products 事件（不等 LLM）
        6. 流式生成文字回答（通道B）
        7. 异步抓取价格并推送 products_update（通道A 第二阶段）
        8. 输出来源、免责声明、done
        """
        ctx = ChatContext(message=message, request_id=request_id)

        try:
            # ---- 阶段 1：并行启动意图识别和平台搜索 ----
            yield {"event": "status", "data": {"stage": "analyzing", "message": "正在分析您的问题..."}}

            # 意图识别与平台搜索并行执行，减少整体延迟
            intent_task = asyncio.create_task(intent_service.classify(message))
            products_task = (
                asyncio.create_task(search_all_platforms(message))
                if _PLATFORM_API_AVAILABLE else None
            )

            # 等待意图识别（通常比平台搜索更快完成）
            ctx.intent = await intent_task
            logger.info("意图识别完成: %s", ctx.intent.intent)

            # ---- 超出范围处理 ----
            if ctx.intent.intent == "out_of_scope":
                if products_task:
                    products_task.cancel()
                yield {"event": "delta", "data": {"text": "我目前专注于保险咨询。您如果想了解重疾险、医疗险、条款解读或产品对比，我可以继续帮您。"}}
                yield {"event": "done", "data": {"requestId": request_id}}
                return

            # ---- 追问处理 ----
            if ctx.intent.needs_followup:
                if products_task:
                    products_task.cancel()
                followup_text = await answer_service.generate_followup(
                    message, ctx.intent.missing_slots
                )
                yield {"event": "delta", "data": {"text": followup_text}}
                yield {"event": "done", "data": {"requestId": request_id}}
                return

            # ---- 阶段 2：根据意图处理产品搜索结果 ----
            need_products = ctx.intent.intent in _PRODUCT_SEARCH_INTENTS

            yield {"event": "status", "data": {"stage": "searching", "message": "正在搜索保险产品..."}}

            if need_products and products_task:
                # 通道A：等待平台直连 API 搜索结果（已在后台并行执行）
                try:
                    ctx.products = await products_task
                except asyncio.CancelledError:
                    ctx.products = []
                except Exception as exc:
                    logger.warning("平台搜索失败: %s", exc)
                    ctx.products = []

                if ctx.products:
                    yield {
                        "event": "products",
                        "data": {"items": [p.model_dump() for p in ctx.products]},
                    }
            else:
                # 不需要产品搜索，取消后台任务
                if products_task:
                    products_task.cancel()
                ctx.products = []

            # 通道B：fallback 知识库作为 LLM 上下文
            ctx.search_results = []
            for q in [message][:2]:
                ctx.search_results.extend(search_service._fallback_search(q))

            # ---- 阶段 4：去重来源 ----
            seen_urls: set[str] = set()
            unique_sources: list[SourceItem] = []
            for r in ctx.search_results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    unique_sources.append(SourceItem(title=r.title, url=r.url, site=r.site))
            ctx.sources = unique_sources

            # ---- 阶段 5：流式生成文字回答（通道B） ----
            yield {"event": "status", "data": {"stage": "answering", "message": "正在生成回答..."}}

            try:
                async for chunk in answer_service.generate_stream(
                    message, ctx.intent.intent, ctx.search_results
                ):
                    yield {"event": "delta", "data": {"text": chunk}}
            except Exception as llm_exc:
                # LLM 超时/异常时降级：推送提示文案，不中断整个流
                logger.warning("LLM 回答生成失败，降级处理: %s", llm_exc)
                yield {
                    "event": "delta",
                    "data": {"text": "抱歉，回答生成超时。请查看上方的产品卡片了解详情，或稍后重试。"},
                }

            # ---- 阶段 6（平台直连 API 已包含价格，无需异步抓取） ----

            # ---- 阶段 7：输出来源、免责声明、done ----
            if ctx.sources:
                yield {
                    "event": "sources",
                    "data": {
                        "items": [s.model_dump() for s in ctx.sources]
                    },
                }

            yield {
                "event": "disclaimer",
                "data": {"text": "以上信息仅供参考，具体保障内容请以保险合同条款为准。"},
            }

            yield {"event": "done", "data": {"requestId": request_id}}

        except Exception as exc:
            logger.error("编排链路异常: %s", exc, exc_info=True)
            error_code = getattr(exc, "code", "INTERNAL_ERROR")
            error_message = getattr(exc, "message", str(exc))
            yield {
                "event": "error",
                "data": {
                    "code": error_code,
                    "message": error_message,
                    "requestId": request_id,
                },
            }


# 全局单例
chat_orchestrator = ChatOrchestrator()
