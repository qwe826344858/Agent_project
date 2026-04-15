"""对话主接口 — POST /api/chat（SSE 流式响应）"""

import json
import uuid

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.core.errors import InvalidArgumentError
from app.schemas.chat import ChatRequest
from app.services.orchestrator_adapter import get_orchestrator

router = APIRouter()


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """
    对话主接口，使用 SSE 流式返回回答。

    SSE 事件类型：
    - status: 处理阶段状态
    - delta: 增量回答文本
    - sources: 来源列表
    - disclaimer: 免责声明
    - done: 完成
    - error: 错误
    """
    # 参数校验：有 action 时允许 message 为空
    if not body.action and (not body.message or not body.message.strip()):
        raise InvalidArgumentError("message 不能为空")

    # 生成 requestId
    request_id = body.request_id or getattr(request.state, "request_id", str(uuid.uuid4()))

    async def event_generator():
        """消费编排器的流式输出，转换为 SSE 事件"""
        # 通过适配层获取当前编排器实现
        orchestrator = get_orchestrator()
        async for event_dict in orchestrator.run_chat_flow(
            message=body.message.strip() if body.message else "",
            request_id=request_id,
            action=body.action,
            product_url=body.product_url,
            product_name=body.product_name,
        ):
            event_type = event_dict.get("event", "delta")
            event_data = event_dict.get("data", {})

            yield {
                "event": event_type,
                "data": json.dumps(event_data, ensure_ascii=False),
            }

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-Id": request_id,
        },
    )
