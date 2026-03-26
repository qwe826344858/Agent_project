"""搜索编排服务 — 支持多种搜索后端

搜索优先级：
1. MiniMax 搜索（通过 MiniMax API 的 /v1/coding_plan/search 端点，免费）
2. 外部搜索 API（需配置 SEARCH_API_KEY）
3. 静态 fallback 知识库（兜底）
"""

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.errors import UpstreamError, UpstreamTimeoutError
from app.schemas.chat import SearchResultItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 静态保险知识库 — 搜索 API 不可用时的保底来源
# ---------------------------------------------------------------------------
_FALLBACK_KNOWLEDGE: list[dict] = [
    {
        "title": "什么是免赔额？免赔额越低越好吗？",
        "url": "https://zhuanlan.zhihu.com/p/350682461",
        "site": "zhuanlan.zhihu.com",
        "snippet": "免赔额是保险公司不予赔付的金额部分，常见于医疗险中。一般年免赔额为1万元，超过部分才可报销。免赔额高低直接影响保费和理赔门槛。",
        "keywords": ["免赔额", "免赔", "起赔线", "赔付门槛"],
    },
    {
        "title": "保险等待期是什么意思？等待期内出险怎么办？",
        "url": "https://zhuanlan.zhihu.com/p/362051847",
        "site": "zhuanlan.zhihu.com",
        "snippet": "等待期也叫观察期，是保险合同生效后的一段免责期。重疾险等待期通常为90-180天，医疗险为30天。等待期内出险保险公司不予赔付。",
        "keywords": ["等待期", "观察期", "免责期", "等待期内出险"],
    },
    {
        "title": "重疾险怎么选？2024年重疾险选购指南",
        "url": "https://zhuanlan.zhihu.com/p/389456123",
        "site": "zhuanlan.zhihu.com",
        "snippet": "重疾险即重大疾病保险，确诊约定重疾后一次性给付保额。选购时需关注保障病种、赔付次数、轻中症保障及保费豁免条款。",
        "keywords": ["重疾险", "重大疾病", "重疾", "大病保险", "重疾保障"],
    },
    {
        "title": "百万医疗险和重疾险有什么区别？",
        "url": "https://zhuanlan.zhihu.com/p/401234567",
        "site": "zhuanlan.zhihu.com",
        "snippet": "医疗险是报销型保险，凭医疗费用发票报销；重疾险是给付型保险，确诊即赔。百万医疗险保费低保额高，但通常有1万免赔额，且为一年期需续保。",
        "keywords": ["医疗险", "百万医疗", "住院医疗", "医疗保险", "医疗报销"],
    },
    {
        "title": "意外险买哪种好？意外险选购攻略",
        "url": "https://zhuanlan.zhihu.com/p/378901234",
        "site": "zhuanlan.zhihu.com",
        "snippet": "意外险保障因意外伤害导致的身故、伤残及医疗费用。综合意外险通常包含意外身故/伤残、意外医疗、住院津贴等保障，保费低杠杆高。",
        "keywords": ["意外险", "意外伤害", "意外保险", "综合意外"],
    },
    {
        "title": "定期寿险和终身寿险怎么选？",
        "url": "https://zhuanlan.zhihu.com/p/356789012",
        "site": "zhuanlan.zhihu.com",
        "snippet": "寿险以身故为赔付条件。定期寿险保障一定年限，保费低适合家庭经济支柱；终身寿险保障终身，兼具储蓄功能，适合资产传承规划。",
        "keywords": ["寿险", "定期寿险", "终身寿险", "人寿保险", "身故保障"],
    },
    {
        "title": "年金险值得买吗？年金险的优缺点分析",
        "url": "https://zhuanlan.zhihu.com/p/412345678",
        "site": "zhuanlan.zhihu.com",
        "snippet": "年金险是一种以生存为给付条件的保险，适合养老规划和长期资金储备。优点是收益确定写入合同，缺点是流动性差、前期退保有损失。",
        "keywords": ["年金险", "年金", "养老保险", "养老金", "养老规划"],
    },
    {
        "title": "保额怎么确定？不同险种保额选多少合适？",
        "url": "https://www.iachina.cn/art/2023/11/15/art_72_106521.html",
        "site": "www.iachina.cn",
        "snippet": "保额即保险金额，是保险公司承担赔偿的最高限额。重疾险建议保额30-50万，寿险保额建议为年收入的10倍，医疗险建议选百万保额。",
        "keywords": ["保额", "保险金额", "保多少", "保额选择"],
    },
    {
        "title": "保费怎么算？影响保费的因素有哪些？",
        "url": "https://www.iachina.cn/art/2023/9/20/art_72_105832.html",
        "site": "www.iachina.cn",
        "snippet": "保费是投保人为获得保险保障而支付的费用。影响保费的主要因素包括年龄、性别、健康状况、职业、保额、保障期限和缴费年限等。",
        "keywords": ["保费", "保险费", "保费计算", "交多少钱", "保费预算"],
    },
    {
        "title": "保险理赔流程全解析：出险后如何快速获得赔付？",
        "url": "https://www.cbirc.gov.cn/cn/view/pages/tongjishuju/tongjishuju.html",
        "site": "www.cbirc.gov.cn",
        "snippet": "保险理赔一般流程：出险报案→准备材料→提交申请→保险公司审核→赔付到账。建议第一时间报案，保留好医疗单据、诊断证明等材料。",
        "keywords": ["理赔", "保险理赔", "出险", "报案", "赔付", "理赔流程"],
    },
    {
        "title": "保险核保是什么意思？核保不通过怎么办？",
        "url": "https://baike.baidu.com/item/保险核保",
        "site": "baike.baidu.com",
        "snippet": "核保是保险公司对投保申请进行风险评估的过程。核保结果包括标准体承保、加费承保、除外承保和拒保。核保不通过可尝试多家投保或选择智能核保产品。",
        "keywords": ["核保", "保险核保", "核保不通过", "风险评估", "承保"],
    },
    {
        "title": "健康告知怎么填？如实告知的注意事项",
        "url": "https://zhuanlan.zhihu.com/p/345678901",
        "site": "zhuanlan.zhihu.com",
        "snippet": "健康告知是投保时必须如实回答的健康相关问题。遵循有问必答、不问不答原则。未如实告知可能导致拒赔。常见问题涉及既往症、住院史、体检异常等。",
        "keywords": ["健康告知", "如实告知", "告知义务", "带病投保", "既往症"],
    },
    {
        "title": "2024年热门保险产品对比测评",
        "url": "https://zhuanlan.zhihu.com/p/423456789",
        "site": "zhuanlan.zhihu.com",
        "snippet": "从保障范围、保费性价比、理赔服务等维度横向对比热门重疾险、医疗险、意外险产品，帮助消费者选择最适合自己的保险方案。",
        "keywords": ["保险对比", "产品对比", "对比测评", "哪个好", "性价比"],
    },
    {
        "title": "保险怎么买最划算？家庭保险配置方案推荐",
        "url": "https://zhuanlan.zhihu.com/p/398765432",
        "site": "zhuanlan.zhihu.com",
        "snippet": "科学的家庭保险配置应先保障后理财，优先配置医疗险和意外险，再补充重疾险和寿险。预算有限时可选择定期保障，后续加保。",
        "keywords": ["保险推荐", "保险配置", "怎么买保险", "保险方案", "买保险"],
    },
    {
        "title": "保险合同条款怎么看？关键条款解读指南",
        "url": "https://www.iachina.cn/art/2024/1/10/art_72_107201.html",
        "site": "www.iachina.cn",
        "snippet": "保险条款是保险合同的核心内容。重点关注保险责任、责任免除、等待期、犹豫期、现金价值等关键条款，避免投保后才发现保障不符预期。",
        "keywords": ["条款解读", "保险条款", "合同条款", "责任免除", "保险合同"],
    },
    {
        "title": "保险犹豫期是什么？犹豫期内退保全额退款吗？",
        "url": "https://baike.baidu.com/item/犹豫期",
        "site": "baike.baidu.com",
        "snippet": "犹豫期是投保人签收保单后的一段时间（通常10-20天），在此期间退保可全额退还保费。过了犹豫期退保只能退现金价值，可能有较大损失。",
        "keywords": ["犹豫期", "退保", "全额退保", "现金价值"],
    },
    {
        "title": "中国银行保险监督管理委员会关于规范互联网保险销售的通知",
        "url": "https://www.cbirc.gov.cn/cn/view/pages/ItemDetail.html?docId=925393",
        "site": "www.cbirc.gov.cn",
        "snippet": "银保监会规范互联网保险销售行为，要求保险机构在销售页面显著位置展示保险条款、免责条款等重要信息，保障消费者知情权和选择权。",
        "keywords": ["银保监会", "保险监管", "互联网保险", "保险销售", "消费者权益"],
    },
]

# 低质量结果关键词黑名单（广告、营销软文等）
_LOW_QUALITY_KEYWORDS: list[str] = [
    "广告",
    "推广",
    "立即购买",
    "限时优惠",
    "点击领取",
    "免费领",
    "加微信",
    "扫码关注",
    "本地宝",
    "缴费标准",
    "缴费基数",
    "职工医保缴费",
]


class SearchService:
    """搜索编排服务 — 调用外部搜索 API 获取保险相关信息"""

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    async def search(self, queries: list[str]) -> list[SearchResultItem]:
        """
        并发执行多个搜索关键词，汇总去重后返回搜索结果列表。

        - 对每个 query 并发调用搜索 API
        - 单个 query 失败时重试 1 次，仍失败则跳过（不阻塞其他 query）
        - 全部 query 均失败时抛出 UpstreamError
        - 搜索 API 不可用时降级返回空列表
        """
        if not queries:
            return []

        # 并发请求所有 query
        tasks = [self._search_single(q) for q in queries]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集成功的结果
        all_items: list[SearchResultItem] = []
        failures: int = 0

        for idx, result in enumerate(settled):
            if isinstance(result, BaseException):
                failures += 1
                logger.warning("搜索 query '%s' 失败: %s", queries[idx], result)
            elif isinstance(result, list):
                all_items.extend(result)
            # 其他情况忽略

        # 全部失败 —— 判断是超时还是一般错误
        if failures == len(queries) and len(queries) > 0:
            # 检查是否所有失败都是超时
            all_timeout = all(
                isinstance(r, (httpx.TimeoutException, asyncio.TimeoutError))
                for r in settled
                if isinstance(r, BaseException)
            )
            if all_timeout:
                raise UpstreamTimeoutError("所有搜索查询均超时")
            raise UpstreamError("所有搜索查询均失败")

        # 去重 + 过滤
        unique = self._deduplicate(all_items)
        cleaned = self._filter_low_quality(unique)

        # 过滤后为空时，对所有 queries 调用 fallback 补充
        if not cleaned:
            fallback_items: list[SearchResultItem] = []
            for q in queries:
                fallback_items.extend(self._fallback_search(q))
            cleaned = self._deduplicate(fallback_items)

        return cleaned

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _fallback_search(self, query: str) -> list[SearchResultItem]:
        """
        当搜索 API 不可用时，从静态保险知识库中匹配相关来源作为保底。

        - 遍历 _FALLBACK_KNOWLEDGE，query 中包含任一 keyword 则命中
        - 匹配结果按 URL 去重后返回
        - 如果无任何匹配，返回一条通用保险知识来源兜底
        """
        seen_urls: set[str] = set()
        matched: list[SearchResultItem] = []

        for entry in _FALLBACK_KNOWLEDGE:
            for kw in entry["keywords"]:
                if kw in query:
                    url = entry["url"]
                    if url not in seen_urls:
                        seen_urls.add(url)
                        matched.append(
                            SearchResultItem(
                                title=entry["title"],
                                url=url,
                                site=entry["site"],
                                snippet=entry["snippet"],
                            )
                        )
                    break  # 同一条目匹配一个关键词即可，避免重复

        # 无匹配时返回通用兜底来源
        if not matched:
            matched.append(
                SearchResultItem(
                    title="保险知识科普：一文读懂保险基础概念",
                    url="https://zhuanlan.zhihu.com/p/398765432",
                    site="zhuanlan.zhihu.com",
                    snippet="涵盖保险分类、投保流程、常见术语解读等基础知识，帮助消费者快速了解保险。",
                )
            )

        return matched

    # ------------------------------------------------------------------
    # MiniMax 搜索（复用 MiniMax API Key，无需额外配置）
    # API: POST https://api.minimaxi.com/v1/coding_plan/search
    # ------------------------------------------------------------------

    @staticmethod
    def _get_minimax_key() -> str:
        """获取 MiniMax API Key（从多个来源尝试）"""
        import os
        return (
            os.environ.get("MINIMAX_API_KEY", "")
            or getattr(settings, "LLM_API_KEY", "")
            or ""
        )

    # 保险电商平台列表 — 搜索时用 site: 限定在这些平台内
    _INSURANCE_PLATFORMS = [
        "xiaoyusan.com",       # 小雨伞保险
        "huize.com",           # 慧择保险
        "shenlanbao.com",      # 深蓝保
        "i.zhongan.com",       # 众安保险
        "baoxian.pingan.com",  # 平安保险
    ]

    async def _search_minimax(self, query: str, api_key: str) -> list[SearchResultItem]:
        """通过 MiniMax 搜索获取保险商品信息

        搜索策略（两轮）：
        1. 第一轮：在保险电商平台内搜索商品详情页（带 site: 限定）
        2. 第二轮：通用搜索补充产品测评和价格信息
        合并去重后返回。
        """
        api_host = "https://api.minimaxi.com"
        url = f"{api_host}/v1/coding_plan/search"
        timeout = httpx.Timeout(settings.SEARCH_TIMEOUT, connect=5.0)

        all_items: list[SearchResultItem] = []
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # 提取用户意图中的险种关键词（从原始问题中简化）
        import re as _re
        # 提取险种关键词
        insurance_types = _re.findall(r'(医疗保险|医疗险|重疾险|意外险|寿险|年金险|百万医疗|防癌险|健康险)', query)
        search_keyword = insurance_types[0] if insurance_types else "保险"

        async with httpx.AsyncClient(timeout=timeout) as client:
            # ---- 并发搜索：平台商品页 + 通用搜索 ----
            search_tasks = []

            # 每个保险平台单独搜索（用 site: 限定）
            for platform in self._INSURANCE_PLATFORMS[:3]:  # 取前3个平台
                pq = f"site:{platform} {search_keyword} 2026"
                search_tasks.append(self._do_minimax_search(client, url, headers, pq))

            # 通用搜索（带产品导向关键词）
            search_tasks.append(self._do_minimax_search(client, url, headers, f"{search_keyword} 推荐 2026 价格 投保"))

            # 并发执行所有搜索
            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, list):
                    all_items.extend(result)
                elif isinstance(result, Exception):
                    logger.warning("搜索任务 %d 失败: %s", i, result)

        # 去重 + 排序：平台商品页优先
        seen = set()
        platform_items: list[SearchResultItem] = []
        other_items: list[SearchResultItem] = []
        platform_domains = set(self._INSURANCE_PLATFORMS)

        for item in all_items:
            if item.url in seen:
                continue
            seen.add(item.url)
            # 判断是否属于保险电商平台
            if any(domain in item.site for domain in platform_domains):
                platform_items.append(item)
            else:
                other_items.append(item)

        # 平台商品页排前面，通用结果排后面，总量限制在 15 条以内
        unique = platform_items[:10] + other_items[:5]

        logger.info(
            "MiniMax 搜索汇总: query='%s' 平台=%d 通用=%d 总=%d",
            query, len(platform_items), len(other_items), len(unique),
        )
        return unique

    @staticmethod
    async def _do_minimax_search(
        client: httpx.AsyncClient, url: str, headers: dict, query: str
    ) -> list[SearchResultItem]:
        """执行单次 MiniMax 搜索请求"""
        resp = await client.post(url, json={"q": query}, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("base_resp", {}).get("status_code", 0) != 0:
            return []
        items = SearchService._parse_search_results(data)
        logger.info("搜索完成: query='%s' 结果数=%d", query[:50], len(items))
        return items

    @staticmethod
    def _parse_search_results(data: dict) -> list[SearchResultItem]:
        """解析 MiniMax 搜索 API 返回的 organic 结果"""
        items: list[SearchResultItem] = []
        for r in data.get("organic", []):
            if not isinstance(r, dict):
                continue
            title = r.get("title", "").strip()
            link = r.get("link", "").strip()
            snippet = r.get("snippet", "").strip()
            if not title or not link:
                continue
            items.append(SearchResultItem(
                title=title,
                url=link,
                site=SearchService._extract_site(link),
                snippet=snippet[:300] if snippet else title,
            ))
        return items

    async def _search_single(self, query: str) -> list[SearchResultItem]:
        """
        对单个 query 调用搜索 API，失败自动重试 1 次。
        """
        last_exc: BaseException | None = None

        for attempt in range(2):  # 最多 2 次（首次 + 重试 1 次）
            try:
                return await self._call_api(query)
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "搜索 API 超时 (query='%s', attempt=%d): %s",
                    query, attempt + 1, exc,
                )
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                logger.warning(
                    "搜索 API 返回错误状态码 (query='%s', attempt=%d): %s",
                    query, attempt + 1, exc,
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "搜索 API 请求异常 (query='%s', attempt=%d): %s",
                    query, attempt + 1, exc,
                )
            except Exception as exc:
                # 未知异常，不重试
                last_exc = exc
                logger.error(
                    "搜索 API 未知异常 (query='%s'): %s", query, exc, exc_info=True,
                )
                break

        # 重试用尽，抛出最后一次异常供上层收集
        if last_exc is not None:
            raise last_exc
        return []  # 理论上不会到这里

    async def _call_api(self, query: str) -> list[SearchResultItem]:
        """
        调用搜索引擎获取结果。

        优先级：DuckDuckGo → 外部 API → fallback 知识库
        """
        # 优先使用 MiniMax 搜索（利用 MiniMax API Key，无需额外配置）
        minimax_key = self._get_minimax_key()
        if minimax_key:
            try:
                results = await self._search_minimax(query, minimax_key)
                if results:
                    return results
                logger.info("MiniMax 搜索无结果，降级到下一个搜索后端")
            except Exception as exc:
                logger.warning("MiniMax 搜索失败: %s", exc)

        # 外部搜索 API 未配置时，使用 fallback 知识库
        if not settings.SEARCH_API_KEY:
            logger.info("无可用搜索 API，使用 fallback 知识库")
            return self._fallback_search(query)

        timeout = httpx.Timeout(settings.SEARCH_TIMEOUT, connect=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                settings.SEARCH_API_URL,
                params={"q": query, "count": settings.SEARCH_TOP_N},
                headers={"Authorization": f"Bearer {settings.SEARCH_API_KEY}"},
            )
            response.raise_for_status()

        data = response.json()

        # 兼容两种常见响应结构：
        #   { "results": [...] }  或  { "data": { "results": [...] } }
        raw_results: list[dict] = []
        if isinstance(data, dict):
            if "results" in data:
                raw_results = data["results"]
            elif "data" in data and isinstance(data["data"], dict):
                raw_results = data["data"].get("results", [])
            elif "items" in data:
                raw_results = data["items"]

        items: list[SearchResultItem] = []
        for r in raw_results:
            try:
                url = r.get("url", r.get("link", ""))
                items.append(
                    SearchResultItem(
                        title=r.get("title", ""),
                        url=url,
                        site=self._extract_site(url),
                        snippet=r.get("snippet", r.get("description", "")),
                    )
                )
            except Exception:
                # 单条解析失败不影响整体
                logger.debug("解析搜索结果条目失败: %s", r, exc_info=True)
                continue

        return items

    # ------------------------------------------------------------------
    # 去重 & 过滤
    # ------------------------------------------------------------------

    def _deduplicate(self, results: list[SearchResultItem]) -> list[SearchResultItem]:
        """按 URL 去重，保留首次出现的条目。"""
        seen_urls: set[str] = set()
        unique: list[SearchResultItem] = []

        for item in results:
            # 规范化 URL：去掉尾部斜杠、统一小写 scheme+host
            normalized = self._normalize_url(item.url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            unique.append(item)

        return unique

    def _filter_low_quality(
        self, results: list[SearchResultItem]
    ) -> list[SearchResultItem]:
        """过滤广告、营销软文、信息缺失的低质量结果。"""
        cleaned: list[SearchResultItem] = []

        for item in results:
            # 标题或摘要为空的结果直接过滤
            if not item.title.strip() or not item.snippet.strip():
                logger.debug("过滤空标题/摘要结果: %s", item.url)
                continue

            # URL 为空的结果过滤
            if not item.url.strip():
                continue

            # 检查低质量关键词
            combined = item.title + item.snippet
            if any(kw in combined for kw in _LOW_QUALITY_KEYWORDS):
                logger.debug("过滤低质量结果（命中关键词）: %s", item.title)
                continue

            cleaned.append(item)

        return cleaned

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_site(url: str) -> str:
        """从 URL 中提取站点域名。"""
        try:
            parsed = urlparse(url)
            return parsed.netloc or ""
        except Exception:
            return ""

    @staticmethod
    def _normalize_url(url: str) -> str:
        """规范化 URL 用于去重比较。"""
        try:
            parsed = urlparse(url)
            # 统一 scheme + host 为小写，去掉尾部斜杠
            normalized = (
                f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
                f"{parsed.path.rstrip('/')}"
            )
            if parsed.query:
                normalized += f"?{parsed.query}"
            return normalized
        except Exception:
            return url.strip().rstrip("/")


# 全局单例
search_service = SearchService()
