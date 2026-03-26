"""调试小雨伞 API cookie 获取"""
import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

with httpx.Client(timeout=10, follow_redirects=True) as client:
    # 访问首页
    r1 = client.get("https://www.xiaoyusan.com/", headers={"User-Agent": UA})
    print(f"首页: {r1.status_code}")
    print(f"Cookies: {dict(client.cookies)}")

    # 访问搜索页
    r2 = client.get("https://www.xiaoyusan.com/index/searchindex", headers={"User-Agent": UA})
    print(f"\n搜索页: {r2.status_code}")
    print(f"Cookies: {dict(client.cookies)}")

    # 调 API
    r3 = client.post(
        "https://www.xiaoyusan.com/index/searchData",
        data="searchType=0&level=1&scene=h5list&searchText=医疗&page=1",
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.xiaoyusan.com/index/searchindex",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    print(f"\nAPI: {r3.status_code}")
    print(f"Response: {r3.text[:300]}")
