"""通用 HTML 清洗模块 — 将任意网页 HTML 转为 LLM 友好的纯文本"""

import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 需要完全删除的标签（含内容）
REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "iframe", "noscript", "svg", "img", "link", "meta"}

# 中文字符正则
_CN_RE = re.compile(r'[\u4e00-\u9fff]')

# 最大文本长度（中文字符数）
MAX_CN_CHARS = 5000
TAIL_CN_CHARS = 1000


def clean_html(raw_html: str) -> tuple[str, int]:
    """通用 HTML 清洗，返回 (纯文本, 中文字符数)

    清洗规则：
    1. 优先提取 script 中的内嵌 JSON 数据（SPA 页面常见）
    2. 删除 script/style/nav/footer 等噪音标签
    3. 提取所有文本内容
    4. 合并 HTML 文本和内嵌 JSON 文本
    5. 合并连续空行
    6. 统计中文字符数
    7. 超长文本截断
    """
    if not raw_html or not raw_html.strip():
        return "", 0

    # 先提取 SPA 页面中 script 内嵌的 JSON 数据
    embedded_text = _extract_embedded_json(raw_html)

    soup = BeautifulSoup(raw_html, "html.parser")

    # 删除噪音标签
    for tag in soup.find_all(list(REMOVE_TAGS)):
        tag.decompose()

    # 提取纯文本
    html_text = soup.get_text(separator="\n", strip=True)

    # 合并 HTML 文本和内嵌 JSON 文本
    text = (embedded_text + "\n\n" + html_text) if embedded_text else html_text

    # 合并连续空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 统计中文字符数
    cn_count = len(_CN_RE.findall(text))

    # 文本截断
    text = _truncate_text(text, cn_count)

    logger.info("HTML 清洗完成: 中文 %d 字, %d 字符 (内嵌JSON: %s)",
                cn_count, len(text), "有" if embedded_text else "无")
    return text, cn_count


# 内嵌 JSON 提取模式
_EMBEDDED_JSON_RE = re.compile(r'var\s+\w+\s*=\s*(\{.+?\})\s*;', re.DOTALL)


def _extract_embedded_json(raw_html: str) -> str:
    """从 script 标签的内嵌 JSON 中提取中文文本

    SPA 保险网站（小雨伞/慧择等）将产品数据内嵌在
    <script>var staticData = {...}</script> 中，
    直接删除 script 会丢失这些关键保障信息。
    """
    import json as json_module

    results = []
    for match in _EMBEDDED_JSON_RE.finditer(raw_html):
        json_str = match.group(1)
        if not _CN_RE.search(json_str):
            continue
        try:
            data = json_module.loads(json_str)
            texts = _extract_text_values(data)
            if texts:
                results.extend(texts)
        except (json_module.JSONDecodeError, RecursionError):
            continue

    return "\n".join(results) if results else ""


def _extract_text_values(obj, depth: int = 0) -> list[str]:
    """递归提取 JSON 对象中所有含中文的字符串值"""
    if depth > 10:
        return []
    texts = []
    if isinstance(obj, str):
        if _CN_RE.search(obj) and len(obj) < 500:
            texts.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            texts.extend(_extract_text_values(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(_extract_text_values(item, depth + 1))
    return texts


def _truncate_text(text: str, cn_count: int) -> str:
    """按中文字符数截断文本

    策略：
    - ≤ 5000 中文字符：不截断
    - 5000-10000：保留前 5000 字符的对应文本
    - > 10000：前 5000 + 末尾 1000
    """
    if cn_count <= MAX_CN_CHARS:
        return text

    # 找到第 MAX_CN_CHARS 个中文字符的位置
    head_pos = _find_cn_char_position(text, MAX_CN_CHARS)

    if cn_count <= MAX_CN_CHARS * 2:
        return text[:head_pos]

    # 超长文本：头部 + 尾部
    tail_pos = _find_cn_char_position_reverse(text, TAIL_CN_CHARS)
    return text[:head_pos] + "\n\n...(中间内容省略)...\n\n" + text[tail_pos:]


def _find_cn_char_position(text: str, n: int) -> int:
    """找到第 n 个中文字符在文本中的位置"""
    count = 0
    for i, ch in enumerate(text):
        if _CN_RE.match(ch):
            count += 1
            if count >= n:
                return i + 1
    return len(text)


def _find_cn_char_position_reverse(text: str, n: int) -> int:
    """从末尾往前找到第 n 个中文字符的位置"""
    count = 0
    for i in range(len(text) - 1, -1, -1):
        if _CN_RE.match(text[i]):
            count += 1
            if count >= n:
                return i
    return 0
