"""Open-WebSearch MCP 搜索引擎对比调试脚本

用法：docker exec compose-backend-1 python3 tests/debug_mcp_engines.py
"""

import json
import threading
import time

import httpx

MCP_BASE = "http://web-search:3000"

ENGINES_TO_TEST = [
    ["bing"],
    ["baidu"],
]

QUERIES_TO_TEST = [
    "医疗险 保险 小雨伞 投保",
    "小雨伞保险 百万医疗",
    "慧择保险 百万医疗险",
    "百万医疗险 2026 推荐 投保",
    "平安保险 百万医疗 产品",
]


def mcp_search(query, engines, limit=8):
    session_url = None
    responses = []
    stop = threading.Event()
    ready = threading.Event()

    def listener():
        nonlocal session_url
        try:
            with httpx.Client(timeout=60) as c:
                with c.stream("GET", f"{MCP_BASE}/sse") as r:
                    for line in r.iter_lines():
                        if stop.is_set():
                            break
                        if line.startswith("data: /messages"):
                            session_url = line[6:].strip()
                            ready.set()
                        elif line.startswith("data: {"):
                            try:
                                responses.append(json.loads(line[6:]))
                            except:
                                pass
        except:
            pass
        finally:
            ready.set()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    if not ready.wait(timeout=8) or not session_url:
        stop.set()
        return 0, []

    url = f"{MCP_BASE}{session_url}"
    with httpx.Client(timeout=30) as c:
        c.post(url, json={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                           "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                      "clientInfo": {"name": "debug", "version": "1"}}})
        time.sleep(0.3)
        c.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        time.sleep(0.3)
        start = time.time()
        c.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "search",
                                      "arguments": {"query": query, "limit": limit, "engines": engines}}})

    for _ in range(60):
        time.sleep(0.5)
        for d in responses:
            if d.get("id") == 1 and "result" in d:
                elapsed = round(time.time() - start, 2)
                results = []
                for ct in d["result"].get("content", []):
                    if ct.get("type") == "text":
                        try:
                            results = json.loads(ct["text"]).get("results", [])
                        except:
                            pass
                stop.set()
                return elapsed, results
    stop.set()
    return round(time.time() - start, 2), []


def main():
    print("=" * 70)
    print("Open-WebSearch MCP 搜索调试 (Playwright mode)")
    print("=" * 70)

    # Bing Playwright vs Baidu request 对比
    print("\n>>> 第一轮：固定搜索词，对比引擎")
    test_q = "医疗险 保险 小雨伞 投保"
    for engines in ENGINES_TO_TEST:
        elapsed, results = mcp_search(test_q, engines)
        print(f"\n  引擎: {engines}  耗时: {elapsed}s  结果: {len(results)}条")
        for r in results[:5]:
            eng = r.get("engine", "?")
            print(f"    [{eng}] {r.get('title', '')[:50]}")
            print(f"         {r.get('url', '')[:70]}")

    # 不同搜索词用 Bing Playwright
    print(f"\n\n>>> 第二轮：Bing Playwright，对比搜索词")
    for q in QUERIES_TO_TEST:
        elapsed, results = mcp_search(q, ["bing"])
        print(f"\n  搜索词: {q}")
        print(f"  耗时: {elapsed}s  结果: {len(results)}条")
        for r in results[:3]:
            print(f"    {r.get('title', '')[:50]}")
            print(f"    {r.get('url', '')[:70]}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
