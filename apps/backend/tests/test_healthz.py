"""健康检查接口测试"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_healthz_returns_200():
    """测试 /api/healthz 返回 200 状态码"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/healthz")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_healthz_status_ok():
    """测试响应包含 status='ok'"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/healthz")
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "backend"
        # 验证 time 字段存在且不为空
        assert "time" in data
        assert len(data["time"]) > 0
