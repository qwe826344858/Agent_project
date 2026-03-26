"""调试百度移动端搜索 HTML 解析"""
import httpx
import re

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://m.baidu.com/",
}

r = httpx.get(
    "https://m.baidu.com/s",
    params={"word": "达尔文10号重疾险"},
    headers=headers,
    timeout=10,
    follow_redirects=True,
)
print(f"STATUS: {r.status_code}")
print(f"HTML_LEN: {len(r.text)}")

# 方案1: article 标签
articles = re.findall(
    r'<article[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>\s*<div[^>]*>(.*?)</div>',
    r.text, re.DOTALL,
)
print(f"ARTICLES: {len(articles)}")

# 方案2: data-log a 标签
data_logs = re.findall(
    r'<a[^>]*data-log[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
    r.text, re.DOTALL,
)
print(f"DATA_LOGS: {len(data_logs)}")
for href, title in data_logs[:5]:
    clean = re.sub(r"<[^>]+>", "", title).strip()
    if clean and len(clean) > 4:
        print(f"  {clean[:60]} | {href[:80]}")

# 方案3: 通用 href + 标题
generic = re.findall(
    r'href="(https?://[^"]*)"[^>]*>\s*(?:<h3[^>]*>|<span[^>]*c-title[^>]*>)(.*?)(?:</h3>|</span>)',
    r.text, re.DOTALL,
)
print(f"GENERIC: {len(generic)}")
for href, title in generic[:5]:
    clean = re.sub(r"<[^>]+>", "", title).strip()
    if clean:
        print(f"  {clean[:60]} | {href[:80]}")

# 打印 HTML 片段用于分析结构
print("\n=== HTML 摘要（前3000字符）===")
print(r.text[:3000])
