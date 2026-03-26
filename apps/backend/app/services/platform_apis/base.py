"""保险平台 API 抽象基类

新增平台只需继承 PlatformAPI 并实现 search() 方法。
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.chat import ProductCard

logger = logging.getLogger(__name__)

# ======================================================================
# 险种关键词映射（用户输入 → 平台搜索词）
# ======================================================================

KEYWORD_MAPPING: dict[str, str] = {
    # 医疗类
    "医疗保险": "医疗",
    "医疗险": "医疗",
    "百万医疗": "医疗",
    "百万医疗险": "医疗",
    "健康险": "医疗",
    "住院医疗": "医疗",
    "补充医疗": "医疗",
    "高端医疗": "医疗",
    # 重疾类
    "重疾险": "重疾",
    "重大疾病": "重疾",
    "重大疾病险": "重疾",
    "大病险": "重疾",
    "大病保险": "重疾",
    # 意外类
    "意外险": "意外",
    "意外保险": "意外",
    "意外伤害": "意外",
    "综合意外": "意外",
    # 寿险类
    "寿险": "寿险",
    "人寿保险": "寿险",
    "定期寿险": "定期寿险",
    "终身寿险": "终身寿险",
    "定寿": "定期寿险",
    # 年金类
    "年金险": "年金",
    "年金保险": "年金",
    "养老险": "养老",
    "养老保险": "养老",
    "养老金": "养老",
    # 教育金类
    "教育金": "教育金",
    "教育金保险": "教育金",
    "教育险": "教育金",
    # 防癌类
    "防癌险": "防癌",
    "防癌医疗": "防癌",
    "防癌医疗险": "防癌",
    # 少儿类
    "少儿险": "少儿",
    "少儿保险": "少儿",
    "儿童保险": "少儿",
    "儿童险": "少儿",
    # 旅游类
    "旅游险": "旅游",
    "旅行险": "旅游",
    "旅游保险": "旅游",
    # 车险类
    "车险": "车险",
    "汽车保险": "车险",
    # 家财类
    "家财险": "家财",
    "家庭财产保险": "家财",
}

# ======================================================================
# 险种正则（按长度降序排列，优先匹配更长的词）
# ======================================================================

INSURANCE_TYPE_RE = re.compile(
    r"(百万医疗险|百万医疗|住院医疗|补充医疗|高端医疗|医疗保险|医疗险|"
    r"重大疾病险|重大疾病|大病保险|大病险|重疾险|"
    r"意外伤害|意外保险|综合意外|意外险|"
    r"家庭财产保险|家财险|"
    r"定期寿险|终身寿险|人寿保险|寿险|"
    r"年金保险|年金险|养老保险|养老险|养老金|"
    r"教育金保险|教育金|教育险|"
    r"防癌医疗险|防癌医疗|防癌险|"
    r"少儿保险|少儿险|儿童保险|儿童险|"
    r"旅游保险|旅行险|旅游险|"
    r"汽车保险|车险|"
    r"健康险)"
)

# ======================================================================
# 人群/场景 → 险种映射
# ======================================================================

AUDIENCE_MAPPING: dict[str, list[str]] = {
    # 少儿
    "宝宝": ["少儿医疗", "少儿重疾", "少儿意外"],
    "孩子": ["少儿医疗", "少儿重疾", "少儿意外"],
    "小孩": ["少儿医疗", "少儿重疾", "少儿意外"],
    "儿童": ["少儿医疗", "少儿重疾", "少儿意外"],
    "婴儿": ["少儿医疗", "少儿重疾", "少儿意外"],
    "新生儿": ["少儿医疗", "少儿重疾", "少儿意外"],
    # 老人
    "老人": ["医疗", "防癌", "意外"],
    "老年": ["医疗", "防癌", "意外"],
    "退休": ["医疗", "防癌", "意外"],
    # 家庭
    "全家": ["医疗", "意外", "重疾"],
    "家庭": ["医疗", "意外", "重疾"],
    "一家人": ["医疗", "意外", "重疾"],
    # 父母
    "父母": ["医疗", "防癌", "意外"],
    "爸妈": ["医疗", "防癌", "意外"],
    "爸爸妈妈": ["医疗", "防癌", "意外"],
    # 就医场景
    "住院": ["医疗"],
    "生病": ["医疗"],
    "看病": ["医疗"],
    "手术": ["医疗"],
    # 养老场景
    "养老": ["年金", "养老"],
    # 教育场景
    "教育": ["教育金", "少儿重疾"],
    "上学": ["教育金", "少儿重疾"],
    # 身故/猝死场景
    "猝死": ["意外", "寿险"],
    "身故": ["意外", "寿险"],
    "去世": ["意外", "寿险"],
}

# 人群/场景正则（按长度降序排列）
_AUDIENCE_KEYS_SORTED = sorted(AUDIENCE_MAPPING.keys(), key=len, reverse=True)
AUDIENCE_RE = re.compile(
    r"(" + "|".join(re.escape(k) for k in _AUDIENCE_KEYS_SORTED) + r")"
)

# 年龄正则
AGE_RE = re.compile(r"(\d{1,3})\s*岁")

# 简单预算正则（用于 base.py 内部兜底，避免循环导入）
_BUDGET_RE_PATTERNS = [
    re.compile(r"预算[每]?[年]?\s*(\d+\.?\d*)"),
    re.compile(r"(\d+\.?\d*)\s*[元块]?\s*[/每]?\s*年"),
    re.compile(r"年[预]?[算费]?\s*(\d+\.?\d*)"),
    re.compile(r"(\d+\.?\d*)\s*[元块]左右"),
    re.compile(r"(\d+\.?\d*)\s*[元块]以内"),
]


def _extract_budget_simple(user_input: str) -> Optional[float]:
    """从用户输入中提取预算数字（简化版）

    为避免与 __init__.py 中的 _extract_budget 循环导入，
    此处仅做最基本的数字提取。支持"万"单位。
    """
    for pat in _BUDGET_RE_PATTERNS:
        m = pat.search(user_input)
        if m:
            val = float(m.group(1))
            if val <= 0:
                continue
            # 检查匹配内容附近是否有"万"
            end_pos = m.end()
            if end_pos < len(user_input) and user_input[end_pos] == "万":
                val *= 10000
            # 合理性检查
            if 50 <= val <= 100000:
                return val
    return None


class PlatformAPI(ABC):
    """保险平台 API 抽象基类"""

    name: str = ""       # 平台名称（如 "小雨伞"）
    domain: str = ""     # 平台域名（如 "xiaoyusan.com"）

    @abstractmethod
    async def search(self, keyword: str, page: int = 1) -> list[ProductCard]:
        """搜索产品，返回标准 ProductCard 列表

        Args:
            keyword: 搜索关键词（如 "医疗"、"重疾"）
            page: 页码

        Returns:
            ProductCard 列表，每个包含真实的投保链接和价格
        """
        ...

    def extract_keywords(self, user_input: str) -> list[str]:
        """从用户输入中提取多个平台搜索词（多关键词提取引擎）

        提取优先级：
        1. 正则匹配险种关键词（INSURANCE_TYPE_RE）
        2. 人群/场景推断险种（AUDIENCE_MAPPING）
        3. 兜底策略（按预算/年龄/默认）

        Returns:
            去重且保序的关键词列表
        """
        keywords: list[str] = []
        seen: set[str] = set()

        # ---- 第 1 层：正则直接匹配险种关键词 ----
        matches = INSURANCE_TYPE_RE.findall(user_input)
        for raw in matches:
            mapped = KEYWORD_MAPPING.get(raw, raw)
            if mapped not in seen:
                seen.add(mapped)
                keywords.append(mapped)

        # ---- 第 2 层：人群/场景推断 ----
        audience_kws = self._extract_audience_keywords(user_input)
        for kw in audience_kws:
            if kw not in seen:
                seen.add(kw)
                keywords.append(kw)

        # ---- 第 3 层：兜底 ----
        if not keywords:
            fallback_kws = self._fallback_keywords(user_input)
            for kw in fallback_kws:
                if kw not in seen:
                    seen.add(kw)
                    keywords.append(kw)

        return keywords

    def extract_keyword(self, user_input: str) -> str:
        """从用户输入中提取平台搜索词（兼容旧接口，取第一个关键词）"""
        keywords = self.extract_keywords(user_input)
        return keywords[0] if keywords else "保险"

    def _extract_audience_keywords(self, user_input: str) -> list[str]:
        """从人群/场景描述中推断险种关键词

        Returns:
            去重且保序的关键词列表
        """
        keywords: list[str] = []
        seen: set[str] = set()

        matches = AUDIENCE_RE.findall(user_input)
        for aud in matches:
            for kw in AUDIENCE_MAPPING.get(aud, []):
                if kw not in seen:
                    seen.add(kw)
                    keywords.append(kw)

        return keywords

    def _extract_age(self, user_input: str) -> Optional[int]:
        """从用户输入中提取年龄

        匹配格式如：28岁、3 岁、65岁
        Returns:
            年龄数字，未找到返回 None
        """
        m = AGE_RE.search(user_input)
        if m:
            age = int(m.group(1))
            if 0 <= age <= 150:
                return age
        return None

    def _fallback_keywords(self, user_input: str) -> list[str]:
        """终极兜底：根据预算或年龄推断险种关键词

        优先级：
        1. 有预算：按金额分层推荐
        2. 有年龄：按年龄段推荐
        3. 都没有：返回通用组合
        """
        # 尝试提取预算
        budget = _extract_budget_simple(user_input)
        if budget is not None:
            if budget <= 500:
                return ["意外", "医疗"]
            elif budget <= 3000:
                return ["医疗", "意外", "重疾"]
            else:
                return ["重疾", "医疗", "寿险"]

        # 尝试提取年龄
        age = self._extract_age(user_input)
        if age is not None:
            if age < 18:
                return ["少儿医疗", "少儿意外"]
            elif age >= 55:
                return ["医疗", "防癌"]
            else:
                return ["医疗", "重疾", "意外"]

        # 都没有 → 通用兜底
        return ["医疗", "重疾", "意外"]
