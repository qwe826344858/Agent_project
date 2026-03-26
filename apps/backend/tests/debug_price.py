"""调试：通过搜索获取产品价格"""
import httpx
import os
import re

api_key = os.environ.get("MINIMAX_API_KEY", "")
if not api_key:
    print("ERROR: MINIMAX_API_KEY not set")
    exit(1)

product = "众安尊享e生百万医疗险 2026"
query = f"{product} 保费 多少钱一年"
print(f"Query: {query}")

try:
    r = httpx.post(
        "https://api.minimaxi.com/v1/coding_plan/search",
        json={"q": query},
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=10,
    )
    data = r.json()
    print(f"Status: {data.get('base_resp', {}).get('status_code')}")

    for i, item in enumerate(data.get("organic", [])[:5]):
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        text = title + " " + snippet
        print(f"\n[{i}] {title[:60]}")
        print(f"    snippet: {snippet[:100]}")

        # 尝试价格正则
        patterns = [
            (r"(\d+\.?\d*)\s*元/年", "{val}元/年"),
            (r"[¥￥]\s*(\d+\.?\d*)", "¥{val}"),
            (r"(\d+\.?\d*)\s*元起", "{val}元起"),
            (r"(\d+\.?\d*)\s*元/月", "{val}元/月"),
            (r"保费[约为是：:]*\s*(\d+\.?\d*)", "{val}元"),
            (r"(\d+)\s*[-~至到]\s*(\d+)\s*元", "{val}元"),
        ]
        for pat, fmt in patterns:
            m = re.search(pat, text)
            if m:
                print(f"    PRICE MATCH: {fmt.format(val=m.group(1))}")
                break
        else:
            print("    NO PRICE MATCH")

except Exception as e:
    print(f"ERROR: {e}")
