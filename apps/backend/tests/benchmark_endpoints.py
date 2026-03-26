"""MiniMax 多端点响应速度对比测试

对比 Anthropic 协议（国内站）和 OpenAI 协议（国际站）的响应延迟。
"""
import asyncio
import os
import time

import litellm

litellm.suppress_debug_info = True

API_KEY = os.environ.get("MINIMAX_API_KEY", "")

ENDPOINTS = [
    {
        "name": "国内站-OpenAI协议",
        "model": "openai/MiniMax-M2.5",
        "api_base": "https://api.minimaxi.com/v1",
    },
    {
        "name": "国内站-Anthropic协议",
        "model": "anthropic/MiniMax-M2.5",
        "api_base": "https://api.minimaxi.com/anthropic",
    },
]

TEST_MESSAGES = [
    [{"role": "user", "content": "什么是免赔额？用一句话回答。"}],
]

ROUNDS = 2


async def test_endpoint(ep: dict, messages: list[dict]) -> dict:
    """测试单个端点"""
    start = time.monotonic()
    ttft = None
    total = None
    error = None

    try:
        # 非流式调用测速
        resp = await litellm.acompletion(
            model=ep["model"],
            messages=messages,
            api_key=API_KEY,
            api_base=ep["api_base"],
            temperature=0.2,
            timeout=30,
            stream=False,
        )
        total = time.monotonic() - start
        content = resp.choices[0].message.content[:80]
    except Exception as e:
        total = time.monotonic() - start
        error = str(e)[:100]
        content = ""

    # 流式调用测 TTFT
    try:
        start2 = time.monotonic()
        resp_stream = await litellm.acompletion(
            model=ep["model"],
            messages=messages,
            api_key=API_KEY,
            api_base=ep["api_base"],
            temperature=0.2,
            timeout=30,
            stream=True,
        )
        async for chunk in resp_stream:
            if chunk.choices[0].delta and chunk.choices[0].delta.content:
                ttft = time.monotonic() - start2
                break
    except Exception as e:
        if not error:
            error = f"stream: {str(e)[:80]}"

    return {
        "name": ep["name"],
        "total": round(total, 2) if total else None,
        "ttft": round(ttft, 2) if ttft else None,
        "error": error,
        "content": content,
    }


async def main():
    if not API_KEY:
        print("ERROR: MINIMAX_API_KEY 未设置")
        return

    print(f"API Key: ***{API_KEY[-4:]}")
    print(f"测试轮次: {ROUNDS}")
    print(f"端点数: {len(ENDPOINTS)}")
    print("=" * 70)

    results = {ep["name"]: {"totals": [], "ttfts": [], "errors": 0} for ep in ENDPOINTS}

    for round_num in range(1, ROUNDS + 1):
        print(f"\n--- 第 {round_num}/{ROUNDS} 轮 ---")
        for ep in ENDPOINTS:
            for msgs in TEST_MESSAGES:
                r = await test_endpoint(ep, msgs)
                name = r["name"]
                if r["error"]:
                    results[name]["errors"] += 1
                    print(f"  [{name}] FAIL: {r['error']}")
                else:
                    results[name]["totals"].append(r["total"])
                    if r["ttft"]:
                        results[name]["ttfts"].append(r["ttft"])
                    ok_total = "✓" if r["total"] and r["total"] < 15 else "✗"
                    ok_ttft = "✓" if r["ttft"] and r["ttft"] < 3 else "✗"
                    print(f"  [{name}] Total={r['total']}s {ok_total} | TTFT={r['ttft']}s {ok_ttft}")

    # 汇总
    print("\n" + "=" * 70)
    print("端点性能对比报告")
    print("=" * 70)
    for ep in ENDPOINTS:
        name = ep["name"]
        data = results[name]
        totals = data["totals"]
        ttfts = data["ttfts"]
        errors = data["errors"]
        print(f"\n{name}:")
        if totals:
            avg_total = sum(totals) / len(totals)
            avg_ttft = sum(ttfts) / len(ttfts) if ttfts else 0
            print(f"  完整响应: 平均={avg_total:.2f}s  最快={min(totals):.2f}s  最慢={max(totals):.2f}s")
            if ttfts:
                print(f"  首字时间: 平均={avg_ttft:.2f}s  最快={min(ttfts):.2f}s  最慢={max(ttfts):.2f}s")
        print(f"  失败次数: {errors}/{ROUNDS}")


if __name__ == "__main__":
    asyncio.run(main())
