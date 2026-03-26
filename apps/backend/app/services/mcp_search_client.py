"""Open-WebSearch MCP 搜索客户端

MCP Streamable HTTP 协议：SSE 连接必须保持打开，POST 请求通过独立 HTTP 客户端发送。
"""

import json
import logging
import threading
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.schemas.chat import SearchResultItem

logger = logging.getLogger(__name__)


class MCPSearchClient:
    """Open-WebSearch MCP HTTP 客户端

    维持一个持久的 SSE 连接，通过独立 HTTP 请求发送 JSON-RPC。
    搜索结果通过 SSE 流返回。
    """

    def __init__(self) -> None:
        self.base_url: str = settings.MCP_SEARCH_URL
        self.engines: list[str] = [
            e.strip() for e in settings.MCP_SEARCH_ENGINES.split(",") if e.strip()
        ]

    def search(self, query: str, limit: int = 5) -> list[SearchResultItem]:
        """同步搜索（供 asyncio.run_in_executor 调用）"""
        session_url = None
        sse_responses: list[dict] = []
        sse_ready = threading.Event()
        stop_event = threading.Event()

        def sse_listener():
            """后台线程：保持 SSE 连接，收集所有响应"""
            nonlocal session_url
            try:
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                    with client.stream("GET", f"{self.base_url}/sse") as resp:
                        for line in resp.iter_lines():
                            if stop_event.is_set():
                                break
                            if line.startswith("data: /messages"):
                                session_url = line[6:].strip()
                                sse_ready.set()
                            elif line.startswith("data: {"):
                                try:
                                    data = json.loads(line[6:])
                                    sse_responses.append(data)
                                except json.JSONDecodeError:
                                    pass
            except Exception as exc:
                logger.debug("SSE 连接异常: %s", exc)
            finally:
                sse_ready.set()  # 确保不会无限等待

        # 启动 SSE 后台线程
        t = threading.Thread(target=sse_listener, daemon=True)
        t.start()

        # 等待 session endpoint（最多 8 秒）
        if not sse_ready.wait(timeout=8):
            logger.warning("MCP: SSE 连接超时")
            stop_event.set()
            return []

        if not session_url:
            logger.warning("MCP: 未获取到 session URL")
            stop_event.set()
            return []

        full_url = f"{self.base_url}{session_url}"
        logger.info("MCP session: %s", full_url)

        try:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
                # 初始化
                client.post(full_url, json={
                    "jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "smartinsure", "version": "1.0"},
                    },
                })
                time.sleep(0.5)
                client.post(full_url, json={
                    "jsonrpc": "2.0", "method": "notifications/initialized",
                })
                time.sleep(0.3)

                # 发送搜索请求
                client.post(full_url, json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {
                        "name": "search",
                        "arguments": {
                            "query": query,
                            "limit": limit,
                            "engines": self.engines,
                        },
                    },
                })
        except Exception as exc:
            logger.warning("MCP 请求失败: %s", exc)
            stop_event.set()
            return []

        # 等待搜索结果通过 SSE 返回（最多 20 秒）
        for _ in range(40):
            time.sleep(0.5)
            for data in sse_responses:
                if data.get("id") == 1 and "result" in data:
                    stop_event.set()
                    return self._parse_results(data)

        logger.warning("MCP 搜索超时，SSE 响应数: %d", len(sse_responses))
        stop_event.set()
        return []

    def _parse_results(self, data: dict) -> list[SearchResultItem]:
        """解析 MCP 返回的搜索结果"""
        items: list[SearchResultItem] = []

        content_list = data.get("result", {}).get("content", [])
        for content in content_list:
            if content.get("type") != "text":
                continue
            try:
                search_data = json.loads(content["text"])
                for r in search_data.get("results", []):
                    title = r.get("title", "").strip()
                    url = r.get("url", "").strip()
                    desc = r.get("description", "").strip()
                    if not title or not url:
                        continue
                    if any(d in url for d in ["douyin.com", "tiktok.com"]):
                        continue
                    items.append(SearchResultItem(
                        title=title,
                        url=url,
                        site=self._extract_site(url),
                        snippet=desc[:300] if desc else title,
                    ))
            except (json.JSONDecodeError, TypeError):
                continue

        logger.info("MCP 搜索解析: %d 条结果", len(items))
        return items

    @staticmethod
    def _extract_site(url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return ""


mcp_search_client = MCPSearchClient()
