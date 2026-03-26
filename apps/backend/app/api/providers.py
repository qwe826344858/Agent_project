"""LLM Provider 查询接口 — 查看已加载的模型和路由状态"""

from fastapi import APIRouter

from app.core.llm_providers import registry

router = APIRouter()


@router.get("/providers")
async def list_providers():
    """列出所有已加载的 LLM Provider 及其状态"""
    return {
        "providers": registry.list_providers(),
        "available": registry.available_providers,
    }
