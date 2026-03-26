"""健康检查接口"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.chat import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """健康检查端点，返回服务状态和当前时间（ISO 8601 带时区）"""
    now = datetime.now(tz=timezone.utc).isoformat()
    return HealthResponse(status="ok", service="backend", time=now)
