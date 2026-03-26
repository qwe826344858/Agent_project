"""推荐问题接口测试"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_suggestions_returns_200():
    """测试 /api/suggestions 返回 200 状态码"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/suggestions")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_suggestions_list_length():
    """测试 suggestions 数组非空且长度在 3-5 之间"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/suggestions")
        data = response.json()
        suggestions = data["suggestions"]
        assert isinstance(suggestions, list)
        assert 3 <= len(suggestions) <= 5
