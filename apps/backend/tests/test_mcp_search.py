"""测试 Open-WebSearch MCP HTTP 调用

MCP Streamable HTTP 协议：
1. GET /sse 建立持久 SSE 连接（不能关闭）
2. SSE 第一个事件返回 session endpoint: /messages?sessionId=xxx
3. POST /messages?sessionId=xxx 发送 JSON-RPC 请求
4. 响应通过 SSE 流返回
"""
import threading
import time
import json
import httpx

MCP_BASE = "http://localhost:3000"


def test_search():
    session_url = None
    sse_lines = []
    stop_event = threading.Event()

    def sse_listener():
        """后台线程：保持 SSE 连接，收集响应"""
        nonlocal session_url
        try:
            with httpx.Client(timeout=60) as client:
                with client.stream("GET", f"{MCP_BASE}/sse") as resp:
                    for line in resp.iter_lines():
                        if stop_event.is_set():
                            break
                        sse_lines.append(line)
                        if line.startswith("data: /messages"):
                            session_url = line[6:].strip()
        except Exception as e:
            print(f"SSE error: {e}")

    # 启动 SSE 后台线程
    print("1. 启动 SSE 连接 ...")
    t = threading.Thread(target=sse_listener, daemon=True)
    t.start()

    # 等待获取 session URL
    for _ in range(20):
        if session_url:
            break
        time.sleep(0.5)

    if not session_url:
        print("   ERROR: 未获取到 session URL")
        print(f"   SSE lines: {sse_lines}")
        return

    full_url = f"{MCP_BASE}{session_url}"
    print(f"   Session URL: {full_url}")

    with httpx.Client(timeout=30) as client:
        # 初始化
        print("\n2. 初始化 ...")
        resp = client.post(full_url, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        })
        print(f"   status={resp.status_code}")
        if resp.text:
            print(f"   body: {resp.text[:300]}")

        # 等待 SSE 响应
        time.sleep(2)
        print(f"   SSE received: {len(sse_lines)} lines")

        # initialized 通知
        client.post(full_url, json={
            "jsonrpc": "2.0", "method": "notifications/initialized",
        })
        time.sleep(1)

        # tools/list
        print("\n3. 列出工具 ...")
        resp = client.post(full_url, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        print(f"   status={resp.status_code}")
        time.sleep(2)

        # 搜索
        print("\n4. 搜索 '百万医疗险 2026' ...")
        resp = client.post(full_url, json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"query": "百万医疗险 2026 推荐", "limit": 3, "engines": ["bing"]},
            },
        })
        print(f"   status={resp.status_code}")

        # 等待搜索结果通过 SSE 返回
        time.sleep(10)

    # 打印所有 SSE 收到的内容
    stop_event.set()
    print(f"\n=== SSE 收到 {len(sse_lines)} 行 ===")
    for line in sse_lines:
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:].strip())
                print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
            except:
                print(f"  {line[:200]}")


if __name__ == "__main__":
    test_search()
