"""性能基线测量脚本

使用方法:
    python tests/perf_baseline.py --base-url http://localhost:8000 --rounds 3

验收指标:
    - 首字响应时间 (TTFT) < 3 秒
    - 完整响应时间 (Total) < 15 秒
"""

import argparse
import asyncio
import time
import httpx
import json
import statistics


# 测试问题集
TEST_QUESTIONS = [
    "什么是免赔额？",
    "重疾险和医疗险有什么区别？",
    "百万医疗险怎么选？",
]


async def measure_single(client: httpx.AsyncClient, base_url: str, message: str) -> dict:
    """测量单次请求的性能指标

    通过 SSE 流式读取 /api/chat 响应，记录首字时间和完整响应时间。
    """
    start = time.monotonic()
    ttft = None
    total = None
    events = []
    error = None

    try:
        async with client.stream(
            "POST",
            f"{base_url}/api/chat",
            json={"message": message},
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            timeout=30.0,
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                    events.append(event_type)
                    # 收到第一个 delta 事件时记录首字时间
                    if event_type == "delta" and ttft is None:
                        ttft = time.monotonic() - start
                    # 收到 done 事件表示完整响应结束
                    if event_type == "done":
                        total = time.monotonic() - start
                        break
                    # 收到 error 事件也算结束
                    if event_type == "error":
                        total = time.monotonic() - start
                        error = "error event received"
                        break
    except Exception as e:
        total = time.monotonic() - start
        error = str(e)

    return {
        "message": message,
        "ttft": round(ttft, 2) if ttft else None,
        "total": round(total or (time.monotonic() - start), 2),
        "events": events,
        "error": error,
    }


async def run_benchmark(base_url: str, rounds: int):
    """运行性能基线测试"""
    print(f"目标: {base_url}")
    print(f"轮次: {rounds}")
    print(f"问题数: {len(TEST_QUESTIONS)}")
    print("=" * 60)

    all_ttft = []
    all_total = []

    async with httpx.AsyncClient() as client:
        # 先做健康检查，确认服务可达
        try:
            resp = await client.get(f"{base_url}/api/healthz", timeout=5.0)
            if resp.status_code != 200:
                print(f"健康检查失败: {resp.status_code}")
                return
            print("健康检查: OK\n")
        except Exception as e:
            print(f"无法连接: {e}")
            return

        for round_num in range(1, rounds + 1):
            print(f"--- 第 {round_num}/{rounds} 轮 ---")
            for q in TEST_QUESTIONS:
                result = await measure_single(client, base_url, q)
                ttft_str = f"{result['ttft']}s" if result['ttft'] else "N/A"
                status = "PASS" if not result['error'] else f"FAIL({result['error']})"
                ttft_ok = "✓" if result['ttft'] and result['ttft'] < 3 else "✗"
                total_ok = "✓" if result['total'] < 15 else "✗"
                print(f"  [{status}] TTFT={ttft_str} {ttft_ok}  Total={result['total']}s {total_ok}  Q={q[:20]}")

                if result['ttft']:
                    all_ttft.append(result['ttft'])
                all_total.append(result['total'])

    # 汇总统计报告
    print("\n" + "=" * 60)
    print("性能基线报告")
    print("=" * 60)
    if all_ttft:
        print(f"首字时间 (TTFT):")
        print(f"  平均: {statistics.mean(all_ttft):.2f}s")
        print(f"  中位: {statistics.median(all_ttft):.2f}s")
        print(f"  最大: {max(all_ttft):.2f}s")
        print(f"  达标(<3s): {sum(1 for t in all_ttft if t < 3)}/{len(all_ttft)}")
    if all_total:
        print(f"完整响应时间:")
        print(f"  平均: {statistics.mean(all_total):.2f}s")
        print(f"  中位: {statistics.median(all_total):.2f}s")
        print(f"  最大: {max(all_total):.2f}s")
        print(f"  达标(<15s): {sum(1 for t in all_total if t < 15)}/{len(all_total)}")


def main():
    parser = argparse.ArgumentParser(description="Chat API 性能基线测量")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端 API 地址")
    parser.add_argument("--rounds", type=int, default=3, help="测试轮次")
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.base_url, args.rounds))


if __name__ == "__main__":
    main()
