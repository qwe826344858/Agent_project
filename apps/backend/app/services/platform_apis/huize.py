"""慧择保险平台 API

搜索接口：POST https://search.huize.com/api/v4/pc/search/product/list
请求格式：JSON {"pageIndex":1,"pageSize":10,"searchName":"医疗","sortType":1}
响应格式：{"total":142,"data":[{"productName":"...","defaultPrice":32300,...}]}

注意：defaultPrice 单位是分（32300 = 323元）
"""

import logging

import httpx

from app.schemas.chat import ProductCard
from app.services.platform_apis.base import PlatformAPI

logger = logging.getLogger(__name__)


class HuizeAPI(PlatformAPI):
    """慧择保险 API"""

    name = "慧择"
    domain = "huize.com"

    API_URL = "https://search.huize.com/api/v4/pc/search/product/list"

    async def search(self, keyword: str, page: int = 1) -> list[ProductCard]:
        from urllib.parse import quote
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://search.huize.com",
            "Referer": f"https://search.huize.com/chanpin/{quote(keyword)}",
        }

        body = {
            "pageIndex": page,
            "pageSize": 10,
            "searchName": keyword,
            "insureMinAge": None,
            "insureMaxAge": None,
            "sortType": 1,  # 综合排序
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(self.API_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("data", [])
        total = data.get("total", 0)
        logger.info("[慧择] 搜索 '%s' 返回 %d 个产品（共 %d）", keyword, len(items), total)

        products = []
        for item in items:
            product_id = f"hz_{item.get('productId', '')}"
            name = item.get("productName", "")
            pc_url = item.get("pcLocationUrl", "")
            if not name or not pc_url:
                continue

            # 价格：单位是分，转为元
            price_cents = item.get("defaultPrice")
            if price_cents and isinstance(price_cents, (int, float)):
                price_yuan = price_cents / 100
                price_int = int(price_yuan) if price_yuan == int(price_yuan) else price_yuan
                price_str = f"{price_int}元/年起"
            else:
                price_str = None

            # 保险公司
            company = item.get("companyName", "")

            # 产品亮点
            features = item.get("featureContent", [])
            brief = item.get("summary", "") or "；".join(features[:2])

            # 标签
            tags = []
            category = item.get("secondInsuranceCategoryName", "")
            if category:
                tags.append(category)
            # 从投保规则提取关键信息
            for rule in item.get("insuranceRule", []):
                if rule.get("ruleName") == "投保年龄":
                    tags.append(rule.get("ruleValue", ""))
                    break

            products.append(ProductCard(
                id=product_id,
                name=name,
                company=company,
                price=price_str,
                price_label=price_str or "查看详情",
                tags=tags[:3],
                url=pc_url,
                platform=self.name,
                brief=brief,
            ))

        return products
