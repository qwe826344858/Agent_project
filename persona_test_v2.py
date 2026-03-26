#!/usr/bin/env python3
"""扩展多角色测试 v2 — 覆盖更多险种 × 人群组合"""
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
    group: str  # 测试分组
    products_count: int = 0
    products: list = field(default_factory=list)
    text_content: str = ""
    has_markdown: bool = False
    has_sources: bool = False
    has_disclaimer: bool = False
    error: str = ""
    latency_total_ms: int = 0
    events_sequence: list = field(default_factory=list)


PERSONAS = [
    # ===== 第一组：险种精准匹配 =====
    {
        "name": "宝爸（32岁）— 小孩重疾险",
        "group": "险种匹配",
        "query": "我家宝宝3岁了，想给他买一份少儿重疾险，保额50万左右，预算每年2000块，有推荐吗？",
    },
    {
        "name": "企业高管（45岁）— 中年人财富险",
        "group": "险种匹配",
        "query": "我45岁，年收入80万，想了解一下增额终身寿险或者年金险，用来做财富规划和养老储备，预算每年3万",
    },
    {
        "name": "大学生（22岁）— 年轻人意外险",
        "group": "险种匹配",
        "query": "我是大学生，经常骑车上下课，想买一份意外险，最好包含猝死保障，预算200块以内",
    },
    {
        "name": "退休教师（62岁）— 老年人防癌险",
        "group": "险种匹配",
        "query": "我62岁了，有糖尿病，听说普通医疗险买不了，防癌医疗险是不是可以？预算1500一年",
    },
    {
        "name": "新婚夫妻（28岁）— 定期寿险",
        "group": "险种匹配",
        "query": "我刚结婚，背了200万房贷，想买一份定期寿险覆盖房贷风险，保到60岁就行，预算1000元一年",
    },

    # ===== 第二组：家庭综合规划 =====
    {
        "name": "三口之家（30岁夫妻+1岁宝宝）",
        "group": "家庭规划",
        "query": "我和老婆都30岁，宝宝1岁，想给一家三口都买上保险，预算一年8000块，怎么分配比较合理？",
    },
    {
        "name": "四口之家（中产，两个学龄孩子）",
        "group": "家庭规划",
        "query": "我们家四口人，我35岁老婆33岁，大儿子10岁小女儿6岁，家庭年收入50万，全家保险预算1.5万，帮忙规划一下",
    },
    {
        "name": "三代同堂（给父母买保险）",
        "group": "家庭规划",
        "query": "想给我爸妈买保险，爸爸58岁妈妈55岁，身体还可以就是我爸有高血压，预算两个人一年5000块",
    },

    # ===== 第三组：场景化需求 =====
    {
        "name": "外卖骑手（26岁）— 高风险职业",
        "group": "场景需求",
        "query": "我是外卖骑手，每天在路上跑很危险，想买个保险以防万一，预算不多，500块一年吧",
    },
    {
        "name": "自由职业者（30岁）— 无社保补充",
        "group": "场景需求",
        "query": "我是自由职业，没有公司给交社保，想买商业保险来补充，主要怕住院花钱多，预算3000一年",
    },
    {
        "name": "准妈妈（27岁）— 孕期保险",
        "group": "场景需求",
        "query": "我怀孕5个月了，想买一份保险保障孕期和生产风险，另外宝宝出生后也想直接给他上保险",
    },
    {
        "name": "糖尿病患者（50岁）— 带病投保",
        "group": "场景需求",
        "query": "我有2型糖尿病，想买医疗险但很多都拒保了，有没有可以带病投保的产品推荐？预算2000一年",
    },

    # ===== 第四组：知识咨询（不应返回产品） =====
    {
        "name": "保险小白 — 险种区别",
        "group": "知识咨询",
        "query": "重疾险和医疗险有什么区别？都需要买吗？",
    },
    {
        "name": "理赔咨询 — 等待期",
        "group": "知识咨询",
        "query": "什么是等待期？等待期内生病了保险公司赔不赔？",
    },
]


def parse_sse_blocks(raw: str):
    events = []
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
    result = TestResult(
        persona=persona["name"],
        query=persona["query"],
        group=persona["group"],
    )
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
                items = data.get("items", [])
                result.products_count = len(items)
                for p in items[:5]:
                    result.products.append({
                        "name": p.get("name", ""),
                        "price": p.get("price", ""),
                        "platform": p.get("platform", ""),
                        "company": p.get("company", ""),
                        "tags": p.get("tags", []),
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

    md_markers = ["**", "- ", "1.", "###", "> ", "| "]
    result.has_markdown = any(m in result.text_content for m in md_markers)

    return result


def main():
    results = []
    total = len(PERSONAS)
    for i, persona in enumerate(PERSONAS):
        print(f"\n[{i+1}/{total}] {persona['group']} | {persona['name']}")
        print(f"    提问: {persona['query'][:50]}...")
        r = test_persona(persona)
        results.append(r)
        status = "✅" if not r.error else "❌"
        print(f"    {status} 产品: {r.products_count}款 | 文字: {len(r.text_content)}字 | Markdown: {r.has_markdown} | 耗时: {r.latency_total_ms}ms")
        if r.error:
            print(f"    ❌ 错误: {r.error}")

    output = []
    for r in results:
        output.append({
            "persona": r.persona,
            "group": r.group,
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

    with open("/home/peiqi/tmp/Agent/persona_test_v2_results.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 测试完成: {total} 个角色, 结果已保存")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
