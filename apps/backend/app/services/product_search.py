"""产品搜索服务 — 从保险电商平台搜索真实商品页面并提取信息

通过 MiniMax Search API 对保险电商平台执行 site: 搜索，
过滤文章类页面后提取产品名称、平台、URL 等信息，
再异步抓取商品详情页补充价格和保障摘要。
"""

import asyncio
import hashlib
import logging
import os
import re
from typing import Optional

import httpx

from app.core.config import settings
from app.schemas.chat import ProductCard

logger = logging.getLogger(__name__)


class ProductSearchService:
    """产品搜索服务 — 从保险电商平台搜索真实商品页面"""

    # 支持的保险电商平台（白名单模式：只有 URL 匹配 product_url_pattern 的才保留）
    # 新增平台只需追加一条记录，product_url_pattern 为商品详情页的 URL 正则
    PLATFORMS = [
        {
            "domain": "xiaoyusan.com",
            "name": "小雨伞",
            # /insurance/detail?id=177318
            "product_url_pattern": r"xiaoyusan\.com/insurance/detail\?id=",
        },
        {
            "domain": "huize.com",
            "name": "慧择",
            # /apps/cps/index/product/detail?prodId=104046
            "product_url_pattern": r"huize\.com/apps/cps/index/product/detail",
        },
        {
            "domain": "shenlanbao.com",
            "name": "深蓝保",
            # /pingce/961572049333334016（产品测评含投保入口）
            "product_url_pattern": r"shenlanbao\.com/pingce/\d+",
        },
        {
            "domain": "baoxian.pingan.com",
            "name": "平安保险",
            # /product/xxx.shtml 或 /pa18shopnst/.../productInfo/
            "product_url_pattern": r"baoxian\.pingan\.com/product/\w+\.shtml|baoxian\.pingan\.com/pa18shopnst/.*productInfo",
        },
        {
            "domain": "i.zhongan.com",
            "name": "众安保险",
            # /product/ 商品页
            "product_url_pattern": r"zhongan\.com/product/",
        },
    ]

    # 险种关键词正则
    _INSURANCE_TYPE_RE = re.compile(
        r"(百万医疗|医疗保险|医疗险|重疾险|意外险|寿险|年金险|防癌险|健康险)"
    )

    # 模糊关键词到精准搜索词的映射
    _KEYWORD_MAPPING: dict[str, str] = {
        "医疗保险": "百万医疗险",
        "医疗险": "百万医疗险",
        "健康险": "百万医疗险",
    }

    # 价格匹配正则（按优先级排列）
    _PRICE_PATTERNS = [
        re.compile(r"(\d+\.?\d*)\s*元/年"),
        re.compile(r"¥\s*(\d+\.?\d*)"),
        re.compile(r"(\d+\.?\d*)\s*元起"),
        re.compile(r"首月\s*(\d+\.?\d*)\s*元"),
    ]

    # 最大返回产品数量
    MAX_PRODUCTS = 5

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    async def search_products(self, keyword: str) -> list[ProductCard]:
        """搜索保险平台商品页面，返回产品卡片基础信息

        使用 MiniMax Search API 对各平台执行 site: 搜索，
        从结果中筛选匹配白名单的商品页 URL，HEAD 校验后返回。
        """
        api_key = self._get_minimax_key()
        if not api_key:
            logger.warning("未配置 MINIMAX_API_KEY，无法执行产品搜索")
            return []

        # 提取险种关键词
        matches = self._INSURANCE_TYPE_RE.findall(keyword)
        raw_keyword = matches[0] if matches else "保险"
        search_keyword = self._KEYWORD_MAPPING.get(raw_keyword, raw_keyword)

        # 对每个平台并发搜索（MiniMax Search API）
        tasks = [
            self._search_platform_minimax(api_key, platform, f"site:{platform['domain']} {search_keyword} 2026")
            for platform in self.PLATFORMS
        ]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        # 白名单筛选
        all_product_patterns = [p["product_url_pattern"] for p in self.PLATFORMS if p.get("product_url_pattern")]
        candidates: list[ProductCard] = []
        seen_urls: set[str] = set()

        for idx, result in enumerate(settled):
            if isinstance(result, BaseException):
                logger.warning("平台 %s 搜索失败: %s", self.PLATFORMS[idx]["name"], result)
                continue
            if not isinstance(result, list):
                continue
            for r in result:
                url = r.get("link", "")
                if not url or url in seen_urls:
                    continue
                # 白名单匹配
                if not any(re.search(pat, url) for pat in all_product_patterns):
                    continue
                seen_urls.add(url)
                platform = self.PLATFORMS[idx]
                card = self._extract_product_info(r.get("title", ""), url, r.get("snippet", ""), platform)
                candidates.append(card)

        logger.info("搜索到 %d 个商品页候选（白名单过滤后）", len(candidates))

        if not candidates:
            return []

        # HEAD 校验
        verified = await self._verify_urls(candidates[: self.MAX_PRODUCTS + 2])
        products = verified[: self.MAX_PRODUCTS]
        logger.info("产品搜索完成: keyword='%s' 候选=%d 校验=%d 最终=%d", search_keyword, len(candidates), len(verified), len(products))
        return products

    async def enrich_products(self, products: list[ProductCard]) -> list[ProductCard]:
        """异步抓取商品详情页，补充价格和保障摘要

        并发抓取每个产品的 URL，用正则匹配价格信息。
        抓取失败时 price_label 设为"查看详情"。
        超时 5 秒。
        """
        if not products:
            return products

        tasks = [self._fetch_price(p) for p in products]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ProductCard] = []
        for item in enriched:
            if isinstance(item, ProductCard):
                results.append(item)
            elif isinstance(item, BaseException):
                logger.warning("产品详情抓取异常: %s", item)
                # 异常时跳过该产品（已在 _fetch_price 内部兜底，此处极少触发）

        return results

    # ------------------------------------------------------------------
    # URL 可访问性校验（HEAD 请求）
    # ------------------------------------------------------------------

    async def _verify_urls(self, products: list[ProductCard]) -> list[ProductCard]:
        """并发校验商品 URL 的可访问性，过滤已下架的商品

        使用 HEAD 请求，超时 3 秒。
        HTTP 200/301/302 视为在售，其他状态码视为已下架。
        """
        if not products:
            return []

        tasks = [self._check_url(p) for p in products]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verified: list[ProductCard] = []
        for item in results:
            if isinstance(item, ProductCard):
                verified.append(item)
            # BaseException 或 None 表示校验失败，跳过

        logger.info("URL 校验: 总数=%d 通过=%d", len(products), len(verified))
        return verified

    async def _check_url(self, product: ProductCard) -> Optional[ProductCard]:
        """校验单个 URL 是否可访问"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                resp = await client.head(
                    product.url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    follow_redirects=True,
                )
                if resp.status_code < 400:
                    return product
                logger.info("商品页不可访问: %s -> %d", product.url[:60], resp.status_code)
                return None
        except Exception as exc:
            logger.debug("URL 校验失败: %s -> %s", product.url[:60], exc)
            return None

    # ------------------------------------------------------------------
    # 平台搜索
    # ------------------------------------------------------------------

    async def _search_platform(
        self, api_key: str, platform: dict, search_keyword: str
    ) -> list[ProductCard]:
        """对单个平台执行搜索并返回 ProductCard 列表

        优先使用 Open-WebSearch MCP（免费，无配额限制），
        MCP 不可用时回退到 MiniMax Search API。
        """
        query = f"site:{platform['domain']} {search_keyword} 2026"

        # 优先使用 MCP 搜索
        from app.services.mcp_search_client import mcp_search_client
        try:
            loop = asyncio.get_event_loop()
            mcp_results = await loop.run_in_executor(
                None, mcp_search_client.search, query, settings.SEARCH_TOP_N
            )
            if mcp_results:
                logger.info("平台 %s MCP 搜索结果: %d 条", platform["name"], len(mcp_results))
                organic = [{"title": r.title, "link": r.url, "snippet": r.snippet} for r in mcp_results]
            else:
                organic = []
        except Exception as exc:
            logger.warning("MCP 搜索失败，回退到 MiniMax: %s", exc)
            organic = await self._search_platform_minimax(api_key, platform, query)

        logger.info("平台 %s 原始结果数: %d", platform["name"], len(organic))

        products: list[ProductCard] = []
        for r in organic:
            if not isinstance(r, dict):
                continue
            title = r.get("title", "").strip()
            link = r.get("link", "").strip()
            snippet = r.get("snippet", "").strip()
            if not title or not link:
                continue

            # 白名单过滤：URL 必须匹配商品详情页模式
            if not self._is_product_page(link, platform):
                continue

            card = self._extract_product_info(title, link, snippet, platform)
            products.append(card)

        logger.info(
            "平台搜索完成: platform=%s query='%s' 结果数=%d",
            platform["name"],
            query,
            len(products),
        )
        return products

    async def _search_platform_minimax(
        self, api_key: str, platform: dict, query: str
    ) -> list[dict]:
        """MiniMax Search API 回退搜索"""
        if not api_key:
            return []
        api_url = "https://api.minimaxi.com/v1/coding_plan/search"
        timeout = httpx.Timeout(settings.SEARCH_TIMEOUT, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    api_url, json={"q": query},
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
            if data.get("base_resp", {}).get("status_code", 0) != 0:
                return []
            return data.get("organic", [])
        except Exception as exc:
            logger.warning("MiniMax 回退搜索失败: %s", exc)
            return []

    # ------------------------------------------------------------------
    # 页面判断与信息提取
    # ------------------------------------------------------------------

    def _is_product_page(self, url: str, platform: dict) -> bool:
        """白名单模式：URL 必须匹配平台的商品详情页模式

        只有匹配 product_url_pattern 的 URL 才被视为商品页，
        文章页、问答页、测评页全部过滤。
        """
        pattern = platform.get("product_url_pattern", "")
        if not pattern:
            return False
        if re.search(pattern, url):
            return True
        logger.debug("过滤非商品页 URL: %s (不匹配: %s)", url[:80], pattern)
        return False

    # 标题中需要清除的平台后缀
    _TITLE_SUFFIXES_TO_REMOVE = [
        r"[_\-\|]+.*?小雨伞.*$",
        r"[_\-\|]+.*?慧择.*$",
        r"[_\-\|]+.*?深蓝保.*$",
        r"[_\-\|]+.*?众安.*$",
        r"[_\-\|]+.*?沃保.*$",
        r"[_\-\|]+.*?保险网.*$",
        r"[_\-\|]+.*?保险经纪.*$",
    ]

    def _extract_product_info(
        self, title: str, url: str, snippet: str, platform: dict
    ) -> ProductCard:
        """从搜索结果提取 ProductCard 信息"""
        product_id = f"prod_{hashlib.md5(url.encode()).hexdigest()[:8]}"

        # 清洗产品名称：去掉平台后缀、方括号
        clean_name = title.strip()
        clean_name = re.sub(r"^【(.+?)】", r"\1", clean_name)  # 【XX】→ XX
        for suffix_re in self._TITLE_SUFFIXES_TO_REMOVE:
            clean_name = re.sub(suffix_re, "", clean_name).strip()

        # 提取保险公司名
        company = ""
        company_match = re.search(
            r"([\u4e00-\u9fa5]{2,6})(人寿|财险|保险|财产|健康)", clean_name
        )
        if company_match:
            company = company_match.group(0)

        # 简短描述
        brief = snippet[:80] if snippet else ""

        # 提取标签
        tags: list[str] = []
        tag_keywords = [
            "百万医疗", "保证续保", "重疾险", "意外险", "寿险",
            "年金险", "防癌险", "医疗险", "健康险", "0免赔",
            "20年续保", "终身", "长期医疗",
        ]
        combined_text = clean_name + snippet
        for kw in tag_keywords:
            if kw in combined_text and kw not in tags:
                tags.append(kw)

        return ProductCard(
            id=product_id,
            name=clean_name,
            company=company,
            price=None,
            price_label="加载中",
            tags=tags[:3],
            url=url,
            platform=platform["name"],
            brief=brief,
        )

    # ------------------------------------------------------------------
    # 价格抓取与解析
    # ------------------------------------------------------------------

    async def _fetch_price(self, product: ProductCard) -> ProductCard:
        """获取产品详情（价格、保障摘要等）

        策略（按优先级）：
        1. 抓取商品详情页 HTML，用平台专属解析器提取（每个平台有独立的解析逻辑）
        2. 通过 MiniMax 搜索 "{产品名} 保费" 从搜索结果摘要中提取
        3. 都失败则显示"查看详情"
        """
        from app.services.platform_parsers import get_parser

        # 策略 1：抓取商品页 + 平台专属解析
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(
                    product.url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    follow_redirects=True,
                )
            parser = get_parser(product.url)
            detail = parser(resp.text)

            if detail.price:
                product.price = detail.price
                product.price_label = detail.price
            if detail.name and len(detail.name) > len(product.name):
                pass  # 搜索标题通常更准确，不覆盖
            if detail.company and not product.company:
                product.company = detail.company
            if detail.brief and len(detail.brief) > len(product.brief):
                product.brief = detail.brief
            if detail.tags:
                # 合并标签
                for t in detail.tags:
                    if t not in product.tags:
                        product.tags.append(t)
                product.tags = product.tags[:4]

            if product.price:
                logger.info("平台解析成功: %s -> 价格=%s 公司=%s", product.name[:25], product.price, product.company)
                return product
        except Exception as exc:
            logger.debug("商品页抓取失败: %s err=%s", product.url[:60], exc)

        # 策略 2：搜索引擎搜索价格
        api_key = self._get_minimax_key()
        if api_key:
            try:
                price = await self._search_price(api_key, product.name)
                if price:
                    product.price = price
                    product.price_label = price
                    logger.info("从搜索提取到价格: %s -> %s", product.name[:25], price)
                    return product
            except Exception as exc:
                logger.debug("搜索价格失败: %s err=%s", product.name[:20], exc)

        product.price_label = "查看详情"
        logger.info("未提取到价格: %s -> 查看详情", product.name[:25])
        return product

    async def _search_price(self, api_key: str, product_name: str) -> Optional[str]:
        """通过 MiniMax 搜索产品价格信息"""
        query = f"{product_name} 保费 多少钱一年"
        api_url = "https://api.minimaxi.com/v1/coding_plan/search"
        timeout = httpx.Timeout(8.0, connect=3.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                api_url,
                json={"q": query},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("base_resp", {}).get("status_code", 0) != 0:
            return None

        # 从搜索结果的标题和摘要中提取价格
        for r in data.get("organic", [])[:5]:
            text = r.get("title", "") + " " + r.get("snippet", "")
            price = self._parse_price_from_text(text)
            if price:
                return price

        return None

    @staticmethod
    def _parse_price_from_text(html: str) -> Optional[str]:
        """从 HTML 中正则匹配价格信息

        常见格式: 258元/年、¥258、258元起、首月0元 等。
        返回第一个匹配到的价格字符串，未匹配返回 None。
        """
        # 按优先级依次尝试各种价格格式
        patterns_with_format = [
            (re.compile(r"(\d+\.?\d*)\s*元/年"), "{val}元/年"),
            (re.compile(r"¥\s*(\d+\.?\d*)"), "¥{val}"),
            (re.compile(r"(\d+\.?\d*)\s*元起"), "{val}元起"),
            (re.compile(r"首月\s*(\d+\.?\d*)\s*元"), "首月{val}元"),
        ]
        for pattern, fmt in patterns_with_format:
            match = pattern.search(html)
            if match:
                val = match.group(1)
                return fmt.format(val=val)
        return None

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _get_minimax_key() -> str:
        """获取 MiniMax API Key（从环境变量或全局配置中读取）"""
        return (
            os.environ.get("MINIMAX_API_KEY", "")
            or getattr(settings, "LLM_API_KEY", "")
            or ""
        )


# 全局单例
product_search_service = ProductSearchService()
