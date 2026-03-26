"""平安保险平台 API

搜索接口：GET https://baoxian.pingan.com/pa18shopnst/do/era/shopProduct/search?keyword=医疗险
响应格式：{"resultCode":"200","data":[{"productName":"...","productPrice":287.0,...}]}
"""

import logging

import httpx

from app.schemas.chat import ProductCard
from app.services.platform_apis.base import PlatformAPI

logger = logging.getLogger(__name__)

# 平安搜索词映射（平安搜"医疗险"比"医疗"更精准）
_PINGAN_KEYWORD_MAP: dict[str, str] = {
    "医疗": "医疗险",
    "重疾": "重疾险",
    "意外": "意外险",
}


class PinganAPI(PlatformAPI):
    """平安保险 API"""

    name = "平安保险"
    domain = "baoxian.pingan.com"

    API_URL = "https://baoxian.pingan.com/pa18shopnst/do/era/shopProduct/search"

    async def search(self, keyword: str, page: int = 1) -> list[ProductCard]:
        # 平安搜索词需要加"险"后缀
        search_kw = _PINGAN_KEYWORD_MAP.get(keyword, keyword)

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://baoxian.pingan.com/pa18shopnst/nstShop/index.html",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(
                self.API_URL,
                params={"keyword": search_kw},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("resultCode") != "200":
            logger.warning("[平安] API 返回错误: %s", data.get("resultMsg"))
            return []

        items = data.get("data", [])
        logger.info("[平安] 搜索 '%s' 返回 %d 个产品", search_kw, len(items))

        products = []
        for item in items:
            code = item.get("productCode", "")
            product_id = f"pa_{code}"
            name = item.get("productName", "")
            url = item.get("productUrl", "")
            if not name or not url:
                continue

            price_val = item.get("productPrice")
            price_unit = item.get("priceUnit", "")
            if price_val is not None:
                # 287.0 + "/年起" → "287元/年起"
                price_int = int(price_val) if price_val == int(price_val) else price_val
                price_str = f"{price_int}{price_unit}"
            else:
                price_str = None

            desc = item.get("productDesc", "")
            brief = desc.replace("\n", "；") if desc else ""

            products.append(ProductCard(
                id=product_id,
                name=name,
                company="平安保险",
                price=price_str,
                price_label=price_str or "查看详情",
                tags=["平安"],
                url=url,
                platform=self.name,
                brief=brief,
            ))

        return products
