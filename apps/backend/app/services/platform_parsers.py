"""各保险平台商品页面的专属解析器

每个平台的商品详情页结构不同，需要针对性解析。
新增平台只需添加一个解析函数并注册到 PARSERS 字典中。
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ProductDetail:
    """从商品页提取的产品详情"""
    name: Optional[str] = None
    company: Optional[str] = None
    price: Optional[str] = None
    brief: Optional[str] = None
    tags: list[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


# ======================================================================
# 小雨伞解析器
# ======================================================================

def parse_xiaoyusan(html: str) -> ProductDetail:
    """小雨伞商品页解析 — 从 window.staticData JSON 中提取

    数据结构：
    window.staticData = {
        insuranceConfig: { title, productname, productid },
        companyConfig: { companyname },
        versions: { list: [{ duty, coverage }] },
    }
    """
    detail = ProductDetail()

    # 提取 window.staticData（在 <script> 标签中）
    m = re.search(
        r'window\.staticData\s*=\s*(\{.*?\})\s*;?\s*(?:</script>|window\.)',
        html, re.DOTALL,
    )
    if not m:
        # 备选：查找包含 insuranceConfig 的 JSON 片段
        m = re.search(r'(\{"insuranceConfig".*?\})\s*;', html, re.DOTALL)

    if not m:
        logger.debug("小雨伞: 未找到 staticData")
        return _fallback_parse(html, detail)

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        logger.debug("小雨伞: staticData JSON 解析失败")
        return _fallback_parse(html, detail)

    # 提取产品名
    ins_cfg = data.get("insuranceConfig", {})
    detail.name = ins_cfg.get("title") or ins_cfg.get("productname") or None

    # 提取保险公司
    company_cfg = data.get("companyConfig", {})
    detail.company = company_cfg.get("companyname") or None

    # 提取保障信息作为 brief
    versions = data.get("versions", {})
    duty_list = versions.get("list", [])
    brief_parts = []
    for duty in duty_list[:3]:
        name = duty.get("duty", "")
        coverage = duty.get("coverage", "")
        if name and coverage:
            brief_parts.append(f"{name}{coverage}")
    if brief_parts:
        detail.brief = "，".join(brief_parts)

    # 提取标签
    detail.tags = _extract_tags(detail.name or "", detail.brief or "")

    return detail


# ======================================================================
# 平安保险解析器
# ======================================================================

def parse_pingan(html: str) -> ProductDetail:
    """平安保险商品页解析 — 从服务端渲染的 HTML 中提取

    页面特点：价格、产品名、保障额度直接在 HTML 文本中
    """
    detail = ProductDetail()

    # 产品名：<title> 标签或 <h1>
    title_m = re.search(r'<title>(.*?)</title>', html)
    if title_m:
        raw = title_m.group(1).strip()
        # 去掉后缀如 "_平安保险商城"
        raw = re.sub(r'[_\-|].*?(平安|商城).*$', '', raw).strip()
        detail.name = raw

    # 价格：匹配 "XXX元/年" 或 "¥XXX" 或 "XX元起"
    price_patterns = [
        (r'(\d+)\s*元/年', '{val}元/年'),
        (r'[¥￥]\s*(\d+\.?\d*)\s*(?:起|/年)?', '¥{val}'),
        (r'(\d+)\s*元起', '{val}元起'),
    ]
    for pat, fmt in price_patterns:
        pm = re.search(pat, html)
        if pm:
            detail.price = fmt.format(val=pm.group(1))
            break

    # 保险公司
    company_m = re.search(r'(中国平安[\u4e00-\u9fa5]*?保险[\u4e00-\u9fa5]*?公司)', html)
    if company_m:
        detail.company = company_m.group(1)
    else:
        detail.company = "中国平安"

    # 摘要：从 meta description 或保障内容提取
    desc_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.IGNORECASE)
    if desc_m:
        detail.brief = desc_m.group(1)[:100]

    detail.tags = _extract_tags(detail.name or "", detail.brief or "")
    return detail


# ======================================================================
# 慧择解析器
# ======================================================================

def parse_huize(html: str) -> ProductDetail:
    """慧择商品页解析 — 从服务端渲染的 HTML 或嵌入的 JSON 中提取"""
    detail = ProductDetail()

    # 产品名：<title> 标签
    title_m = re.search(r'<title>(.*?)</title>', html)
    if title_m:
        raw = title_m.group(1).strip()
        raw = re.sub(r'\s*-\s*.*?(慧择|保险网).*$', '', raw).strip()
        detail.name = raw

    # 保险公司：从标题或 HTML 中提取
    company_m = re.search(r'([\u4e00-\u9fa5]{2,8})(保险|人寿|财险|健康)', html[:3000])
    if company_m:
        detail.company = company_m.group(0)

    # 价格
    for pat, fmt in [
        (r'(\d+\.?\d*)\s*元/年', '{val}元/年'),
        (r'[¥￥]\s*(\d+\.?\d*)', '¥{val}'),
        (r'(\d+\.?\d*)\s*元起', '{val}元起'),
    ]:
        pm = re.search(pat, html[:5000])
        if pm:
            detail.price = fmt.format(val=pm.group(1))
            break

    # 摘要
    desc_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.IGNORECASE)
    if desc_m:
        detail.brief = desc_m.group(1)[:100]

    detail.tags = _extract_tags(detail.name or "", detail.brief or "")
    return detail


# ======================================================================
# 深蓝保解析器
# ======================================================================

def parse_shenlanbao(html: str) -> ProductDetail:
    """深蓝保商品页（测评页）解析"""
    detail = ProductDetail()

    title_m = re.search(r'<title>(.*?)</title>', html)
    if title_m:
        raw = title_m.group(1).strip()
        raw = re.sub(r'\s*[-_|].*?(深蓝保|测评).*$', '', raw).strip()
        detail.name = raw

    company_m = re.search(r'([\u4e00-\u9fa5]{2,8})(保险|人寿|财险|健康)', html[:3000])
    if company_m:
        detail.company = company_m.group(0)

    for pat, fmt in [
        (r'(\d+\.?\d*)\s*元/年', '{val}元/年'),
        (r'[¥￥]\s*(\d+\.?\d*)', '¥{val}'),
        (r'(\d+\.?\d*)\s*元起', '{val}元起'),
    ]:
        pm = re.search(pat, html[:5000])
        if pm:
            detail.price = fmt.format(val=pm.group(1))
            break

    desc_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.IGNORECASE)
    if desc_m:
        detail.brief = desc_m.group(1)[:100]

    detail.tags = _extract_tags(detail.name or "", detail.brief or "")
    return detail


# ======================================================================
# 众安保险解析器
# ======================================================================

def parse_zhongan(html: str) -> ProductDetail:
    """众安保险商品页解析"""
    detail = ProductDetail()

    title_m = re.search(r'<title>(.*?)</title>', html)
    if title_m:
        raw = title_m.group(1).strip()
        raw = re.sub(r'\s*[-_|].*?(众安|保险).*$', '', raw).strip()
        detail.name = raw

    detail.company = "众安保险"

    for pat, fmt in [
        (r'(\d+\.?\d*)\s*元/年', '{val}元/年'),
        (r'[¥￥]\s*(\d+\.?\d*)', '¥{val}'),
        (r'(\d+\.?\d*)\s*元起', '{val}元起'),
    ]:
        pm = re.search(pat, html[:5000])
        if pm:
            detail.price = fmt.format(val=pm.group(1))
            break

    desc_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.IGNORECASE)
    if desc_m:
        detail.brief = desc_m.group(1)[:100]

    detail.tags = _extract_tags(detail.name or "", detail.brief or "")
    return detail


# ======================================================================
# 通用 fallback 解析
# ======================================================================

def _fallback_parse(html: str, detail: ProductDetail) -> ProductDetail:
    """通用 HTML fallback 解析 — 从 title/meta/正则提取基础信息"""
    if not detail.name:
        title_m = re.search(r'<title>(.*?)</title>', html)
        if title_m:
            detail.name = title_m.group(1).strip()[:60]

    if not detail.price:
        for pat, fmt in [
            (r'(\d+\.?\d*)\s*元/年', '{val}元/年'),
            (r'[¥￥]\s*(\d+\.?\d*)', '¥{val}'),
            (r'(\d+\.?\d*)\s*元起', '{val}元起'),
        ]:
            pm = re.search(pat, html[:5000])
            if pm:
                detail.price = fmt.format(val=pm.group(1))
                break

    if not detail.brief:
        desc_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.IGNORECASE)
        if desc_m:
            detail.brief = desc_m.group(1)[:100]

    detail.tags = _extract_tags(detail.name or "", detail.brief or "")
    return detail


# ======================================================================
# 辅助函数
# ======================================================================

def _extract_tags(name: str, brief: str) -> list[str]:
    """从产品名和摘要中提取标签"""
    tags = []
    combined = name + brief
    tag_keywords = [
        "百万医疗", "保证续保", "重疾险", "意外险", "寿险",
        "年金险", "防癌险", "医疗险", "0免赔", "20年续保",
    ]
    for kw in tag_keywords:
        if kw in combined and kw not in tags:
            tags.append(kw)
    return tags[:3]


# ======================================================================
# 解析器注册表 — 按域名匹配
# ======================================================================

PARSERS: dict[str, callable] = {
    "xiaoyusan.com": parse_xiaoyusan,
    "pingan.com": parse_pingan,
    "huize.com": parse_huize,
    "shenlanbao.com": parse_shenlanbao,
    "zhongan.com": parse_zhongan,
}


def get_parser(url: str) -> callable:
    """根据 URL 域名获取对应的解析器，找不到时返回 fallback"""
    url_lower = url.lower()
    for domain, parser in PARSERS.items():
        if domain in url_lower:
            return parser
    return lambda html: _fallback_parse(html, ProductDetail())
