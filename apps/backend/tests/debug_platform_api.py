"""分析保险平台搜索接口返回的数据结构

小雨伞: https://www.xiaoyusan.com/index/searchindex#/goodsList?word=医疗&type=1
平安: https://baoxian.pingan.com/pa18shopnst/nstShop/index.html#/search?keyword=医疗险
"""
import httpx
import json
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

JSON_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/plain, */*",
}


def test_xiaoyusan():
    """分析小雨伞搜索接口"""
    print("=" * 60)
    print("小雨伞搜索接口分析")
    print("=" * 60)

    # 直接访问搜索页面，看返回的 HTML 中是否有 API 地址或初始数据
    url = "https://www.xiaoyusan.com/index/searchindex"
    r = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
    print(f"\n搜索页面: {r.status_code}, {len(r.text)} bytes")

    # 提取 script 中的 API 地址
    api_urls = re.findall(r'["\']/(api|index|search|goods)[^"\']*["\']', r.text)
    print(f"发现 API 路径: {len(api_urls)}")
    for a in set(api_urls[:10]):
        print(f"  {a}")

    # 提取 JS 文件中可能的 API 地址
    js_files = re.findall(r'src="(/[^"]*\.js[^"]*)"', r.text)
    print(f"\nJS 文件: {len(js_files)}")
    for js in js_files[:5]:
        print(f"  {js}")

    # 尝试常见的搜索 API
    api_candidates = [
        "https://www.xiaoyusan.com/api/search/goods?word=医疗&type=1",
        "https://www.xiaoyusan.com/api/v1/search?word=医疗",
        "https://www.xiaoyusan.com/index/searchGoods?word=医疗&type=1",
        "https://www.xiaoyusan.com/index/goodsList?word=医疗&type=1",
        "https://www.xiaoyusan.com/api/index/searchGoods?word=医疗&type=1",
        "https://www.xiaoyusan.com/api/index/goodsList?word=医疗&type=1",
        "https://www.xiaoyusan.com/search/api/goods?word=医疗",
        "https://www.xiaoyusan.com/searchindex/goodsList?word=医疗&type=1",
    ]

    print("\n尝试 API 端点:")
    for api in api_candidates:
        try:
            r = httpx.get(api, headers=JSON_HEADERS, timeout=5, follow_redirects=True)
            ct = r.headers.get("content-type", "")
            path = api.split(".com")[1][:50]
            print(f"  {r.status_code} [{ct[:25]}] {path}")
            if "json" in ct and r.status_code == 200:
                data = r.json()
                print(f"    KEYS: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                print(f"    DATA: {json.dumps(data, ensure_ascii=False)[:300]}")
        except Exception as e:
            path = api.split(".com")[1][:50]
            print(f"  ERR {path} -> {e}")


def test_pingan():
    """分析平安保险搜索接口"""
    print("\n" + "=" * 60)
    print("平安保险搜索接口分析")
    print("=" * 60)

    # 访问搜索页面
    url = "https://baoxian.pingan.com/pa18shopnst/nstShop/index.html"
    r = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
    print(f"\n搜索页面: {r.status_code}, {len(r.text)} bytes")

    # 提取 API 地址
    api_urls = re.findall(r'["\']/(pa18|api|nst)[^"\']*["\']', r.text)
    print(f"发现 API 路径: {len(api_urls)}")
    for a in set(api_urls[:10]):
        print(f"  {a}")

    # 尝试常见 API
    api_candidates = [
        "https://baoxian.pingan.com/pa18shopnst/api/search?keyword=医疗险",
        "https://baoxian.pingan.com/pa18shopnst/nstShop/api/search?keyword=医疗险",
        "https://baoxian.pingan.com/api/product/search?keyword=医疗险",
        "https://baoxian.pingan.com/pa18shopnst/api/goods/list?keyword=医疗险",
    ]

    print("\n尝试 API 端点:")
    for api in api_candidates:
        try:
            r = httpx.get(api, headers=JSON_HEADERS, timeout=5, follow_redirects=True)
            ct = r.headers.get("content-type", "")
            path = api.split(".com")[1][:50]
            print(f"  {r.status_code} [{ct[:25]}] {path}")
            if "json" in ct and r.status_code == 200:
                data = r.json()
                print(f"    KEYS: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                print(f"    DATA: {json.dumps(data, ensure_ascii=False)[:300]}")
        except Exception as e:
            path = api.split(".com")[1][:50]
            print(f"  ERR {path} -> {e}")


if __name__ == "__main__":
    test_xiaoyusan()
    test_pingan()
