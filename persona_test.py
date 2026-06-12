#!/usr/bin/env python3
"""多角色用户体验测试 — 模拟真实用户向 SmartInsure Agent 发起咨询"""
import json
import time
import re
import requests
from dataclasses import dataclass, field

API_BASE = "http://192.168.2.66:8000"

@dataclass
class TestResult:
    persona: str
    query: str
    products_count: int = 0
    products: list = field(default_factory=list)
    text_content: str = ""
    has_markdown: bool = False
    has_sources: bool = False
    has_disclaimer: bool = False
    error: str = ""
    latency_first_product_ms: int = 0
    latency_first_text_ms: int = 0
    latency_total_ms: int = 0
    events_sequence: list = field(default_factory=list)

PERSONAS = [
    {
        "name": "中产中年男人（38岁，IT主管）",
        "query": "我今年38岁，家里上有老下有小，年收入大概40万，想给自己配一份重疾险+百万医疗险的组合，预算每年5000左右，有什么推荐吗？",
    },
    {
        "name": "刚进入社会的小伙子（23岁，应届生）",
        "query": "刚毕业工作半年，月薪6000，公司有五险一金但感觉不太够，想买个便宜点的保险，预算一年不超过500块，有啥推荐不？",
    },
    {
        "name": "高中生（17岁，学生）",
        "query": "我是高中生，想了解一下保险是什么，为什么大人们都说要买保险呢？学生有必要买保险吗？",
    },
    {
        "name": "准备退休的中老龄人（58岁）",
        "query": "我马上60岁要退休了，身体还行就是有点高血压，想买个医疗险以防万一，不知道这个年纪还能不能买到合适的？预算两三千块一年",
    },
    {
        "name": "小康家庭主妇（35岁）",
        "query": "我们家条件还可以，老公年入30万，我全职带娃。想给全家人都配上保险，两个孩子一个5岁一个8岁，全家预算一年1万块，能帮我规划下吗？",
    },
    {
        "name": "宝妈（28岁，新手妈妈）",
        "query": "宝宝刚出生3个月，想给宝宝买一份保险，主要怕生病住院花钱多。另外我自己产后也想买份保险，预算宝宝1000、我自己1500，求推荐！",
    },
]


def parse_sse_blocks(raw: str):
    """解析 SSE 原始文本为 (event_type, data_dict) 列表"""
    events = []
    # 按双换行分割为 block（兼容 \r\n 和 \n）
    blocks = re.split(r'(?:\r?\n){2,}', raw)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        event_type = ""
        data_str = ""
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
        if event_type and data_str:
            try:
                data = json.loads(data_str)
                events.append((event_type, data))
            except json.JSONDecodeError:
                pass
    return events


def test_persona(persona: dict) -> TestResult:
    result = TestResult(persona=persona["name"], query=persona["query"])
    start = time.time()

    try:
        resp = requests.post(
            f"{API_BASE}/api/chat",
            json={"message": persona["query"]},
            headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
            timeout=60,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        raw = resp.text

        events = parse_sse_blocks(raw)

        for event_type, data in events:
            result.events_sequence.append(event_type)

            if event_type == "products":
                if result.latency_first_product_ms == 0:
                    result.latency_first_product_ms = -1  # 非流式无法精确计时
                items = data.get("items", [])
                result.products_count = len(items)
                for p in items[:5]:
                    result.products.append({
                        "name": p.get("name", ""),
                        "price": p.get("price", ""),
                        "platform": p.get("platform", ""),
                        "url": p.get("url", "")[:80],
                    })
            elif event_type == "delta":
                result.text_content += data.get("text", "")
            elif event_type == "sources":
                result.has_sources = True
            elif event_type == "disclaimer":
                result.has_disclaimer = True
            elif event_type == "error":
                result.error = data.get("message", "unknown error")

    except Exception as e:
        result.error = str(e)

    end = time.time()
    result.latency_total_ms = int((end - start) * 1000)

    # Markdown 格式检测
    md_markers = ["**", "- ", "1.", "###", "> ", "| "]
    result.has_markdown = any(m in result.text_content for m in md_markers)

    return result


def main():
    results = []
    for i, persona in enumerate(PERSONAS):
        print(f"\n[{i+1}/{len(PERSONAS)}] 测试角色: {persona['name']}")
        print(f"    提问: {persona['query'][:50]}...")
        r = test_persona(persona)
        results.append(r)
        print(f"    产品: {r.products_count}款 | 文字: {len(r.text_content)}字 | Markdown: {r.has_markdown} | 耗时: {r.latency_total_ms}ms")
        if r.error:
            print(f"    ❌ 错误: {r.error}")

    # 保存详细 JSON
    output = []
    for r in results:
        output.append({
            "persona": r.persona,
            "query": r.query,
            "products_count": r.products_count,
            "products": r.products,
            "text_length": len(r.text_content),
            "text_content": r.text_content,
            "has_markdown": r.has_markdown,
            "has_sources": r.has_sources,
            "has_disclaimer": r.has_disclaimer,
            "error": r.error,
            "latency_total_ms": r.latency_total_ms,
            "events_sequence": r.events_sequence,
        })

    with open("/home/peiqi/tmp/Agent/persona_test_results.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n✅ 测试完成，结果已保存到 persona_test_results.json")


if __name__ == "__main__":
    main()
