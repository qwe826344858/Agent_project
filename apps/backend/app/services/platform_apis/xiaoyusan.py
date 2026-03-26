"""小雨伞保险平台 API

搜索接口：POST https://www.xiaoyusan.com/index/searchData
请求格式：form-data (searchType=0&level=1&scene=h5list&searchText=医疗&page=1)
响应格式：{"ret":0,"data":{"goodsList":[...],"goodsNum":58}}
"""

import hashlib
import logging
import re

import httpx

from app.schemas.chat import ProductCard
from app.services.platform_apis.base import PlatformAPI

logger = logging.getLogger(__name__)

# 保险公司名称正则（从产品名中提取）
_COMPANY_PATTERNS = [
    "众安保险|众安",
    "中国人保|人保财险|人保健康|人保寿险|人保",
    "中国平安|平安健康|平安人寿|平安",
    "太平洋保险|太平洋产险|太平洋人寿|太平洋",
    "中国人寿|国寿",
    "泰康人寿|泰康在线|泰康",
    "新华保险|新华人寿|新华",
    "阳光保险|阳光人寿|阳光",
    "中英人寿|中英",
    "复星联合|复星",
    "瑞华保险|瑞华",
    "华贵保险|华贵人寿|华贵",
    "中意人寿|中意",
    "信泰人寿|信泰",
    "百年人寿|百年",
    "大家人寿|大家保险",
    "昆仑健康|昆仑",
    "和谐健康|和谐",
    "招商仁和|招商",
    "国富人寿|国富",
    "北京人寿",
    "中邮人寿|中邮",
    "大地保险",
]
_COMPANY_RE = re.compile("|".join(f"(?:{p})" for p in _COMPANY_PATTERNS))


def _extract_company(product_name: str) -> str:
    """从产品名中提取保险公司名称"""
    m = _COMPANY_RE.search(product_name)
    return m.group(0) if m else ""


class XiaoyusanAPI(PlatformAPI):
    """小雨伞保险 API"""

    name = "小雨伞"
    domain = "xiaoyusan.com"

    API_URL = "https://www.xiaoyusan.com/index/searchData"

    async def search(self, keyword: str, page: int = 1) -> list[ProductCard]:
        form_data = {
            "searchType": "0",
            "level": "1",
            "scene": "h5list",
            "searchText": keyword,
            "page": str(page),
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.xiaoyusan.com/index/searchindex",
            "X-Requested-With": "XMLHttpRequest",
        }

        # Cookie 从配置读取（小雨伞 API 需要有效的浏览器 Session）
        import os
        cookie_str = os.environ.get(
            "XYS_COOKIE",
            "acw_tc=0a03174117744064133918697e698da7a4ce8d4e9148bfe5d6e5fb8216af25; PHPSESSID=7d3e01ac2c01c03a6d699507fe504f99; touchurl=https%3A%2F%2Fwww.xiaoyusan.com%2Findex%2Fsearchindex; _xys_fd_id=7d3e01ac2c01c03a6d699507fe504f99; _xys_s_id=2u3dctnckil3kqurhbhr2ozzem1nszz6; SERVERID=73f2dd2c615928dbc5ba783d0df20bdd|1774406413|1774406413; SERVERCORSID=73f2dd2c615928dbc5ba783d0df20bdd|1774406413|1774406413",
        )
        headers["Cookie"] = cookie_str

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), follow_redirects=True) as client:
            resp = await client.post(self.API_URL, data=form_data, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if data.get("ret") != 0:
            logger.warning("[小雨伞] API 返回错误: %s", data.get("msg"))
            return []

        goods_list = data.get("data", {}).get("goodsList", [])
        logger.info("[小雨伞] 搜索 '%s' 返回 %d 个产品", keyword, len(goods_list))

        products = []
        for item in goods_list:
            product_id = f"xys_{item.get('productId', '')}"
            title = item.get("title", "")
            src = item.get("src", "")
            if not title or not src:
                continue

            # 价格：优先 itemPrice（年缴价格），备选 price
            price_val = item.get("itemPrice") or item.get("price", "")
            price_unit = item.get("priceUnit", "")
            price_str = f"{price_val}{price_unit}" if price_val else None

            # 产品亮点
            advantages = item.get("advantage", [])
            brief = "；".join(advantages[:2]) if advantages else ""

            # 标签
            tags = []
            classify = item.get("insuranceClassify", {})
            if classify and classify.get("text"):
                tags.append(classify["text"])
            classify2 = item.get("classify", {})
            if classify2 and classify2.get("text"):
                tags.append(classify2["text"])

            products.append(ProductCard(
                id=product_id,
                name=title,
                company=_extract_company(title),
                price=price_str,
                price_label=price_str or "查看详情",
                tags=tags[:3],
                url=src,
                platform=self.name,
                brief=brief,
            ))

        return products
