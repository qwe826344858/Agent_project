"""保险平台 API 注册表

新增平台：
1. 在本目录新建 xxx.py，继承 PlatformAPI 实现 search()
2. 在下方 PLATFORMS 列表注册
"""

import asyncio
import logging
import re
from typing import Optional

from app.schemas.chat import ProductCard
from app.services.platform_apis.base import PlatformAPI
from app.services.platform_apis.xiaoyusan import XiaoyusanAPI
from app.services.platform_apis.pingan import PinganAPI
from app.services.platform_apis.huize import HuizeAPI

logger = logging.getLogger(__name__)

# ======================================================================
# 预算解析与产品价格估算
# ======================================================================

def _extract_budget(user_input: str) -> Optional[float]:
    """从用户输入中提取年预算（元/年）

    支持格式：
    - "预算1000元"、"预算每年1000"、"年预算1000左右"
    - "1000块"、"1000元左右"
    - "一年1万块"、"预算两三千"、"预算1万"
    """
    patterns = [
        r"预算[每]?[年]?\s*(\d+\.?\d*)\s*万",         # "预算1万" → 10000
        r"预算[每]?[年]?\s*(\d+\.?\d*)",               # "预算1000" → 1000
        r"(\d+\.?\d*)\s*万\s*[元块]?\s*[/每]?\s*年",   # "1万元/年" → 10000
        r"(\d+\.?\d*)\s*[元块]\s*[/每]?\s*年",         # "1000元/年" → 1000
        r"[每一]年\s*(\d+\.?\d*)\s*万\s*[元块]",       # "一年1万块" → 10000
        r"[每一]年\s*(\d+\.?\d*)\s*[元块]",            # "一年1000块" → 1000
        r"年预算\s*(\d+\.?\d*)\s*万",                  # "年预算1万" → 10000
        r"年预算\s*(\d+\.?\d*)",                       # "年预算1000" → 1000
        r"(\d+\.?\d*)\s*万?\s*[元块]左右",             # "1万块左右" → 10000
        r"(\d+\.?\d*)\s*万?\s*[元块]以内",             # "5000块以内" → 5000
        r"不超过\s*(\d+\.?\d*)\s*万?\s*[元块]",       # "不超过500块" → 500
        r"(\d+\.?\d*)\s*[元块]",                      # 通用兜底 "1000元" → 1000
    ]
    for pat in patterns:
        m = re.search(pat, user_input)
        if m:
            val = float(m.group(1))
            if val <= 0:
                continue
            # 判断是否包含"万"单位
            if "万" in m.group(0):
                val *= 10000
            # 合理性检查：年预算应在 50-100000 元范围内
            if val < 50 or val > 100000:
                continue
            logger.info("提取到用户年预算: %.0f 元/年", val)
            return val
    return None


def _estimate_annual_price(price_str: Optional[str]) -> Optional[float]:
    """将产品价格字符串估算为年缴价格（元/年）

    规则：
    - "168元起" / "168元/起" → 168（默认年缴）
    - "287/年起" / "287元/年起" → 287
    - "13.05元/月起" → 13.05 * 12 = 156.6
    - "507元/起" → 507
    - "323元/年起" → 323
    """
    if not price_str:
        return None

    # 提取数字
    num_match = re.search(r"(\d+\.?\d*)", price_str)
    if not num_match:
        return None

    val = float(num_match.group(1))
    if val <= 0:
        return None

    # 判断是月缴还是年缴
    if "月" in price_str:
        return val * 12  # 月缴转年缴

    # 默认当作年缴
    return val


def _filter_by_budget(
    products: list[ProductCard],
    budget: float,
    tolerance: float = 0.5,
    lower_ratio: float = 0.1,
) -> list[ProductCard]:
    """按预算筛选产品

    Args:
        products: 产品列表
        budget: 年预算（元）
        tolerance: 容差比例（0.5 = 允许超出预算 50%）
        lower_ratio: 下限比例（0.1 = 低于预算 10% 视为不相关，家庭场景可用 0.05）

    Returns:
        筛选后的产品列表，按与预算的匹配度排序
    """
    upper_bound = budget * (1 + tolerance)  # 预算上限（含容差）
    lower_bound = budget * lower_ratio      # 价格下限

    scored: list[tuple[float, ProductCard]] = []

    for p in products:
        annual = _estimate_annual_price(p.price)
        if annual is None:
            # 无法估算价格的产品排在最后
            scored.append((999999, p))
            continue

        # 价格过低排除（如预算 500 时，0.2 元的产品不相关）
        if annual < lower_bound:
            logger.debug("价格过低排除: %s (%.0f < %.0f)", p.name, annual, lower_bound)
            continue

        # 超预算排除
        if annual > upper_bound:
            logger.debug("超预算排除: %s (%.0f > %.0f)", p.name, annual, upper_bound)
            continue

        # 在预算范围内，按与预算的差距排序（越接近越靠前）
        diff = abs(annual - budget)
        scored.append((diff, p))

    scored.sort(key=lambda x: x[0])
    result = [p for _, p in scored]

    in_budget = sum(1 for s, _ in scored if s != 999999)
    logger.info(
        "预算筛选: budget=%.0f 下限=%.0f 上限=%.0f 匹配=%d 未知=%d",
        budget, lower_bound, upper_bound, in_budget,
        sum(1 for s, _ in scored if s == 999999),
    )
    return result


# ======================================================================
# 品类过滤 — 过滤与用户意图不相关的产品
# ======================================================================

_IRRELEVANT_CATEGORIES = {
    "旅游险", "旅行险", "自驾游", "境外旅游", "国内旅游",
    "航空意外", "交通意外",
    "责任险", "商业责任", "雇主责任", "亚马逊",
    "财产险", "家财险",
    "车险", "运动保险", "车类运动",
    "留学", "签证",
    "宠物", "手机",
}


def _filter_irrelevant(
    products: list[ProductCard],
    keywords: list[str],
) -> list[ProductCard]:
    """过滤与用户意图不相关的品类

    当用户明确搜索旅游/交通等品类时不过滤。
    """
    # 如果用户明确搜索这些品类，则跳过过滤
    skip_keywords = {"旅游", "交通", "自驾", "留学", "运动", "车险", "家财"}
    if any(kw in skip_keywords for kw in keywords):
        return products

    filtered = []
    for p in products:
        name_and_tags = p.name + " " + " ".join(p.tags)
        is_irrelevant = any(cat in name_and_tags for cat in _IRRELEVANT_CATEGORIES)
        if not is_irrelevant:
            filtered.append(p)

    removed = len(products) - len(filtered)
    if removed > 0:
        logger.info("品类过滤: 移除 %d 个不相关产品", removed)

    return filtered

# ======================================================================
# 年龄适配过滤 — 过滤不匹配用户年龄的产品
# ======================================================================

# 从产品标签/名称中提取年龄范围的正则
_AGE_RANGE_RE = re.compile(r"(\d+)\s*周?岁?\s*[-~至到]\s*(\d+)\s*周?岁")
_CHILD_PRODUCT_RE = re.compile(r"少儿|儿童|宝宝|宝贝|学平|小顽童|大黄蜂")
_SENIOR_PRODUCT_RE = re.compile(r"老年|高龄|银发|孝亲|父母")


def _filter_by_age(
    products: list[ProductCard],
    user_input: str,
) -> list[ProductCard]:
    """根据用户年龄过滤不匹配的产品

    规则：
    - 成人(18-54岁)：过滤明确标注为少儿(0-17岁)或老年(50-80岁)的产品
    - 少儿(<18岁)：过滤明确标注为老年的产品
    - 老年(≥55岁)：过滤明确标注为少儿的产品
    - 家庭场景：不做年龄过滤（全家各年龄段都需要）
    """
    from app.services.platform_apis.base import AGE_RE, AUDIENCE_RE

    # 家庭场景不过滤（全家老小都要覆盖）
    family_keywords = {"全家", "家庭", "一家人", "一家"}
    if any(kw in user_input for kw in family_keywords):
        return products

    # 提取用户年龄
    age_match = AGE_RE.search(user_input)
    if not age_match:
        # 无年龄信息，根据人群/职业关键词推断
        if any(kw in user_input for kw in ("宝宝", "孩子", "小孩", "儿童", "婴儿", "新生儿")):
            user_age_group = "child"
        elif any(kw in user_input for kw in ("退休", "老人", "老年", "父母", "爸妈")):
            user_age_group = "senior"
        elif any(kw in user_input for kw in (
            "大学生", "刚毕业", "应届", "上班族", "骑手", "外卖",
            "自由职业", "打工", "白领", "程序员", "怀孕", "产后",
        )):
            user_age_group = "adult"
        else:
            return products  # 无法判断年龄，不过滤
    else:
        age = int(age_match.group(1))
        if age < 18:
            user_age_group = "child"
        elif age >= 55:
            user_age_group = "senior"
        else:
            user_age_group = "adult"

    filtered = []
    for p in products:
        name_and_tags = p.name + " " + " ".join(p.tags)

        # 从标签中提取年龄范围
        age_range = _AGE_RANGE_RE.search(name_and_tags)
        if age_range:
            min_age = int(age_range.group(1))
            max_age = int(age_range.group(2))

            if user_age_group == "adult" and max_age <= 17:
                # 成人不要纯少儿产品
                logger.debug("年龄过滤: %s (少儿产品, 用户为成人)", p.name)
                continue
            if user_age_group == "adult" and min_age >= 50 and _SENIOR_PRODUCT_RE.search(name_and_tags):
                # 成人不要纯老年产品
                logger.debug("年龄过滤: %s (老年产品, 用户为成人)", p.name)
                continue
            if user_age_group == "child" and min_age >= 18:
                # 少儿不要纯成人产品
                logger.debug("年龄过滤: %s (成人产品, 用户为少儿)", p.name)
                continue
            if user_age_group == "senior" and max_age <= 17:
                # 老年不要少儿产品
                logger.debug("年龄过滤: %s (少儿产品, 用户为老年)", p.name)
                continue
        else:
            # 无年龄范围标签时，用产品名称关键词判断
            if user_age_group == "adult":
                if _CHILD_PRODUCT_RE.search(name_and_tags) and not _AGE_RANGE_RE.search(name_and_tags):
                    logger.debug("年龄过滤: %s (少儿关键词, 用户为成人)", p.name)
                    continue
                if _SENIOR_PRODUCT_RE.search(name_and_tags):
                    logger.debug("年龄过滤: %s (老年关键词, 用户为成人)", p.name)
                    continue
            elif user_age_group == "senior" and _CHILD_PRODUCT_RE.search(name_and_tags):
                logger.debug("年龄过滤: %s (少儿关键词, 用户为老年)", p.name)
                continue
            elif user_age_group == "child" and _SENIOR_PRODUCT_RE.search(name_and_tags):
                logger.debug("年龄过滤: %s (老年关键词, 用户为少儿)", p.name)
                continue

        filtered.append(p)

    removed = len(products) - len(filtered)
    if removed > 0:
        logger.info("年龄过滤: 用户=%s 移除 %d 个不匹配产品", user_age_group, removed)

    return filtered


# ======================================================================
# 家庭场景检测 — 识别家庭人数，用于预算分摊
# ======================================================================

# 家庭场景关键词
_FAMILY_RE = re.compile(r"全家|一家人|家庭|一家\d口")

# 中文数字映射
_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6}
_CN_NUM_CHARS = "一二两三四五六"

# 家庭成员数量提取模式（支持中文/阿拉伯数字）
_FAMILY_SIZE_PATTERNS = [
    re.compile(rf"一家\s*([{_CN_NUM_CHARS}\d])\s*口"),                           # "一家4口"
    re.compile(rf"([{_CN_NUM_CHARS}\d])\s*口之?家"),                              # "4口之家"
    re.compile(rf"([{_CN_NUM_CHARS}\d]+)\s*个?\s*(?:孩子|小孩|娃|宝宝|儿女|子女)"),  # "两个孩子" / "2个小孩"
]


def _parse_cn_or_digit(val: str) -> Optional[int]:
    """将中文数字或阿拉伯数字字符串转为整数"""
    if val in _CN_NUM:
        return _CN_NUM[val]
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _detect_family_size(user_input: str) -> int:
    """检测用户输入中的家庭人数

    如果不是家庭场景或无法识别人数，返回 1（不分摊）。

    策略：
    1. 先检测是否包含家庭关键词
    2. 尝试提取明确人数（"一家4口"）
    3. 推算：提到 N 个孩子 → N + 2（夫妻 + 孩子）
    4. 含家庭关键词但无明确人数 → 默认 3 人
    """
    if not _FAMILY_RE.search(user_input):
        return 1

    # 尝试提取明确的家庭人数
    for pat in _FAMILY_SIZE_PATTERNS[:2]:  # "一家4口" / "4口之家"
        m = pat.search(user_input)
        if m:
            num = _parse_cn_or_digit(m.group(1))
            if num and 2 <= num <= 8:
                logger.info("检测到家庭人数: %d 人", num)
                return num

    # 提取孩子数量 → 推算总人数
    child_pat = _FAMILY_SIZE_PATTERNS[2]
    m = child_pat.search(user_input)
    if m:
        child_count = _parse_cn_or_digit(m.group(1))
        if child_count and 1 <= child_count <= 5:
            total = child_count + 2  # 夫妻 + 孩子
            logger.info("检测到 %d 个孩子，推算家庭人数: %d 人", child_count, total)
            return total

    # 含家庭关键词但无明确人数 → 默认 3 人
    logger.info("检测到家庭场景，默认 3 人")
    return 3


# ======================================================================
# 平台注册表 — 新增平台只需在此追加一行
# ======================================================================

PLATFORMS: list[PlatformAPI] = [
    XiaoyusanAPI(),
    PinganAPI(),
    HuizeAPI(),
    # ShenlanbaoAPI(),   # 深蓝保（待接入）
    # ZhonganAPI(),      # 众安（待接入）
]


async def search_all_platforms(
    user_input: str,
    max_per_platform: int = 10,
    max_total: int = 10,
) -> list[ProductCard]:
    """多关键词并发搜索所有已注册平台，品类过滤 + 预算筛选后返回

    Args:
        user_input: 用户原始输入（含预算信息）
        max_per_platform: 每个平台每个关键词最多取几个产品
        max_total: 最终返回最多几个产品
    """
    if not PLATFORMS:
        return []

    # 三层关键词提取
    keywords = PLATFORMS[0].extract_keywords(user_input)
    keywords = keywords[:3]  # 最多 3 个关键词，控制并发量
    budget = _extract_budget(user_input)
    logger.info(
        "平台搜索: 关键词=%s 预算=%s (用户: '%s')",
        keywords, f"{budget:.0f}元/年" if budget else "未指定", user_input[:40],
    )

    # 每个平台 × 每个关键词 = N 个并发任务
    tasks = []
    for platform in PLATFORMS:
        for kw in keywords:
            tasks.append(_safe_search(platform, kw, max_per_platform))
    results = await asyncio.gather(*tasks)

    # 合并去重（按结果列表交替排列，保证多平台多关键词均衡）
    all_products: list[ProductCard] = []
    seen_names: set[str] = set()
    max_rounds = max((len(r) for r in results), default=0)

    for i in range(max_rounds):
        for result_list in results:
            if i < len(result_list):
                p = result_list[i]
                if p.name not in seen_names:
                    seen_names.add(p.name)
                    all_products.append(p)

    # 品类过滤（移除旅游险、责任险等不相关品类）
    all_products = _filter_irrelevant(all_products, keywords)

    # 年龄适配过滤（移除不匹配用户年龄的产品）
    all_products = _filter_by_age(all_products, user_input)

    # 家庭场景预算分摊：总预算 ÷ 家庭人数 = 单品预算
    is_family = False
    if budget:
        family_size = _detect_family_size(user_input)
        if family_size > 1:
            is_family = True
            per_person_budget = budget / family_size
            logger.info(
                "家庭预算分摊: 总预算=%.0f 家庭人数=%d 人均=%.0f",
                budget, family_size, per_person_budget,
            )
            budget = per_person_budget

    # 预算筛选 + 排序（家庭场景用更宽松的下限）
    if budget:
        lower_ratio = 0.05 if is_family else 0.1
        all_products = _filter_by_budget(all_products, budget, lower_ratio=lower_ratio)

    final = all_products[:max_total]

    logger.info(
        "平台搜索完成: 关键词=%s 预算=%s 平台=%d 总产品=%d 返回=%d",
        keywords,
        f"{budget:.0f}" if budget else "无",
        len(PLATFORMS),
        len(all_products),
        len(final),
    )
    return final


async def _safe_search(
    platform: PlatformAPI, keyword: str, limit: int
) -> list[ProductCard]:
    """安全调用单个平台搜索，异常时返回空列表"""
    try:
        results = await platform.search(keyword)
        logger.info("[%s] 返回 %d 个产品", platform.name, len(results))
        return results[:limit]
    except Exception as exc:
        logger.warning("[%s] 搜索失败: %s", platform.name, exc)
        return []
