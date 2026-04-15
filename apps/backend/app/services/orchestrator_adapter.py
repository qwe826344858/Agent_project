"""编排器适配层 — 通过 ORCHESTRATOR 配置切换编排实现（lite / langgraph）"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class OrchestratorAdapter(ABC):
    """编排器抽象接口 — 所有编排实现必须遵循此接口"""

    @abstractmethod
    async def run_chat_flow(
        self,
        message: str,
        request_id: str = "",
        action: str | None = None,
        product_url: str | None = None,
        product_name: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        执行完整对话编排流程，yield SSE 事件字典。

        事件格式：{"event": "status|delta|sources|disclaimer|done|error", "data": {...}}
        """
        ...


class LiteOrchestrator(OrchestratorAdapter):
    """轻量函数编排实现 — 阶段一默认方案"""

    async def run_chat_flow(
        self,
        message: str,
        request_id: str = "",
        action: str | None = None,
        product_url: str | None = None,
        product_name: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """委托给现有的 ChatOrchestrator.run_stream"""
        from app.services.chat_orchestrator import chat_orchestrator

        async for event in chat_orchestrator.run_stream(
            message=message,
            request_id=request_id,
            action=action,
            product_url=product_url,
            product_name=product_name,
        ):
            yield event


class LangGraphOrchestrator(OrchestratorAdapter):
    """LangGraph 编排实现 — 占位，阶段二实现"""

    async def run_chat_flow(
        self,
        message: str,
        request_id: str = "",
        action: str | None = None,
        product_url: str | None = None,
        product_name: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        yield {
            "event": "error",
            "data": {
                "code": "NOT_IMPLEMENTED",
                "message": "LangGraph 编排尚未实现，请切换为 lite 模式",
                "requestId": request_id,
            },
        }


def get_orchestrator() -> OrchestratorAdapter:
    """根据配置返回对应的编排器实现"""
    from app.core.config import settings

    if settings.ORCHESTRATOR == "langgraph":
        return LangGraphOrchestrator()
    return LiteOrchestrator()
