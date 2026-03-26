"""POST /api/chat 接口自动化测试 + 异常测试"""

import json
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


# ---------------------------------------------------------------------------
# SSE 响应解析辅助函数
# ---------------------------------------------------------------------------

def parse_sse_events(content: str) -> list[dict]:
    """解析 SSE 响应文本为事件列表"""
    events = []
    current_event = None
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current_event:
            data_str = line.split(":", 1)[1].strip()
            try:
                data = json.loads(data_str)
            except (json.JSONDecodeError, ValueError):
                data = data_str
            events.append({"event": current_event, "data": data})
            current_event = None
    return events


# ---------------------------------------------------------------------------
# Mock orchestrator 工厂
# ---------------------------------------------------------------------------

def _make_mock_orchestrator(events: list[dict]):
    """根据给定的事件列表构造一个 mock orchestrator 对象。

    events 中每个元素格式: {"event": "...", "data": {...}}
    """
    async def mock_run_chat_flow(message, request_id=""):
        for evt in events:
            yield evt

    mock_orch = MagicMock()
    mock_orch.run_chat_flow = mock_run_chat_flow
    return mock_orch


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------

class TestChatNormalFlow:
    """正常流程测试"""

    async def test_chat_normal_flow(self):
        """Mock orchestrator yield 完整事件序列，验证响应 200 + 包含所有事件类型"""
        events = [
            {"event": "status", "data": {"stage": "analyzing", "message": "分析中"}},
            {"event": "delta", "data": {"text": "测试回答"}},
            {"event": "sources", "data": {"items": [{"title": "来源", "url": "https://example.com", "site": "example.com"}]}},
            {"event": "disclaimer", "data": {"text": "以上仅供参考"}},
            {"event": "done", "data": {"requestId": "req-001"}},
        ]
        mock_orch = _make_mock_orchestrator(events)

        with patch("app.api.chat.get_orchestrator", return_value=mock_orch):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "什么是重疾险？"},
                )

        # 状态码 200
        assert response.status_code == 200

        # 解析 SSE 事件
        sse_events = parse_sse_events(response.text)

        # 验证包含所有事件类型
        event_types = [e["event"] for e in sse_events]
        for expected_type in ["status", "delta", "sources", "disclaimer", "done"]:
            assert expected_type in event_types, f"缺少事件类型: {expected_type}"

        # 验证 status 事件数据
        status_evt = next(e for e in sse_events if e["event"] == "status")
        assert status_evt["data"]["stage"] == "analyzing"

        # 验证 delta 文本
        delta_evt = next(e for e in sse_events if e["event"] == "delta")
        assert delta_evt["data"]["text"] == "测试回答"

        # 验证 sources 列表
        sources_evt = next(e for e in sse_events if e["event"] == "sources")
        assert len(sources_evt["data"]["items"]) == 1

        # 验证 disclaimer
        disclaimer_evt = next(e for e in sse_events if e["event"] == "disclaimer")
        assert "参考" in disclaimer_evt["data"]["text"]

        # 验证 done 事件
        done_evt = next(e for e in sse_events if e["event"] == "done")
        assert "requestId" in done_evt["data"]


class TestChatInputValidation:
    """输入校验 / 异常测试"""

    async def test_chat_empty_message(self):
        """发送空白消息 message='  '，验证返回 400 + INVALID_ARGUMENT"""
        # Pydantic min_length=1 会拒绝 ""（422），但 "  " 通过 Pydantic 后
        # 会被 chat handler 中的 strip() 校验捕获（400）
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={"message": "   "},
            )

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "INVALID_ARGUMENT"

    async def test_chat_missing_message(self):
        """发送空 JSON {}，验证返回 422（Pydantic 校验失败）"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={},
            )

        assert response.status_code == 422


class TestChatBusinessScenarios:
    """业务场景测试"""

    async def test_chat_out_of_scope(self):
        """Mock orchestrator yield 引导文案，验证 delta 内容包含"保险咨询" """
        events = [
            {"event": "delta", "data": {"text": "抱歉，我只能回答保险咨询相关的问题，请问您有什么保险方面的疑问吗？"}},
            {"event": "done", "data": {"requestId": "req-oos"}},
        ]
        mock_orch = _make_mock_orchestrator(events)

        with patch("app.api.chat.get_orchestrator", return_value=mock_orch):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "今天天气怎么样？"},
                )

        assert response.status_code == 200

        sse_events = parse_sse_events(response.text)
        delta_evt = next(e for e in sse_events if e["event"] == "delta")
        assert "保险咨询" in delta_evt["data"]["text"]

    async def test_chat_followup(self):
        """Mock orchestrator yield 追问话术，验证有 delta 和 done"""
        events = [
            {"event": "delta", "data": {"text": "请问您想了解哪类保险产品？重疾险、医疗险还是意外险？"}},
            {"event": "done", "data": {"requestId": "req-followup"}},
        ]
        mock_orch = _make_mock_orchestrator(events)

        with patch("app.api.chat.get_orchestrator", return_value=mock_orch):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "我想买保险"},
                )

        assert response.status_code == 200

        sse_events = parse_sse_events(response.text)
        event_types = [e["event"] for e in sse_events]
        assert "delta" in event_types, "缺少 delta 事件"
        assert "done" in event_types, "缺少 done 事件"


class TestChatErrorHandling:
    """错误处理测试"""

    async def test_chat_upstream_error(self):
        """Mock orchestrator yield error 事件，验证 event=error + code 字段存在"""
        events = [
            {
                "event": "error",
                "data": {
                    "code": "UPSTREAM_ERROR",
                    "message": "上游服务异常",
                    "requestId": "req-err",
                },
            },
        ]
        mock_orch = _make_mock_orchestrator(events)

        with patch("app.api.chat.get_orchestrator", return_value=mock_orch):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "查询保险方案"},
                )

        assert response.status_code == 200  # SSE 流本身返回 200，错误通过事件传递

        sse_events = parse_sse_events(response.text)
        error_events = [e for e in sse_events if e["event"] == "error"]
        assert len(error_events) >= 1, "应包含 error 事件"
        assert "code" in error_events[0]["data"], "error 事件应包含 code 字段"
        assert error_events[0]["data"]["code"] == "UPSTREAM_ERROR"
