"""多关键词提取引擎 (M1) 单元测试

覆盖 base.py 中的关键词提取、人群推断、年龄提取、兜底策略。
"""

import pytest
import sys
import os

# 将 backend 的 app 目录加入 sys.path，使 import 能正常解析
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.platform_apis.base import (
    KEYWORD_MAPPING,
    INSURANCE_TYPE_RE,
    AUDIENCE_MAPPING,
    AUDIENCE_RE,
    AGE_RE,
    PlatformAPI,
    _extract_budget_simple,
)
from app.schemas.chat import ProductCard


# ======================================================================
# 辅助：创建一个可实例化的 PlatformAPI 子类
# ======================================================================

class _MockPlatform(PlatformAPI):
    """用于测试的 PlatformAPI 具体子类"""
    name = "mock"
    domain = "mock.com"

    async def search(self, keyword: str, page: int = 1) -> list[ProductCard]:
        return []


@pytest.fixture
def platform():
    return _MockPlatform()


# ======================================================================
# 验收标准测试
# ======================================================================

class TestAcceptanceCriteria:
    """验收标准中的 6 个场景"""

    def test_multi_insurance_types(self, platform: _MockPlatform):
        """'重疾险+百万医疗' → ['重疾', '医疗']"""
        result = platform.extract_keywords("重疾险+百万医疗")
        assert result == ["重疾", "医疗"]

    def test_baby_insurance(self, platform: _MockPlatform):
        """'给宝宝买保险' → 包含 '少儿医疗'"""
        result = platform.extract_keywords("给宝宝买保险")
        assert "少儿医疗" in result

    def test_family_plan(self, platform: _MockPlatform):
        """'全家保险规划' → 包含 '医疗', '意外', '重疾'"""
        result = platform.extract_keywords("全家保险规划")
        assert "医疗" in result
        assert "意外" in result
        assert "重疾" in result

    def test_budget_500(self, platform: _MockPlatform):
        """'买个便宜的保险，预算500' → ['意外', '医疗']"""
        result = platform.extract_keywords("买个便宜的保险，预算500")
        assert result == ["意外", "医疗"]

    def test_elderly_medical(self, platform: _MockPlatform):
        """'58岁退休老人买医疗险' → 包含 '医疗'（第一层命中）"""
        result = platform.extract_keywords("58岁退休老人买医疗险")
        assert result[0] == "医疗"  # 第一层正则命中，排第一

    def test_generic_inquiry(self, platform: _MockPlatform):
        """'我想了解下保险' → ['医疗', '重疾', '意外']（兜底）"""
        result = platform.extract_keywords("我想了解下保险")
        assert result == ["医疗", "重疾", "意外"]


# ======================================================================
# extract_keywords 更多测试
# ======================================================================

class TestExtractKeywords:
    """extract_keywords() 方法的扩展测试"""

    def test_single_insurance_type(self, platform: _MockPlatform):
        """单个险种：'我想买意外险' → ['意外']"""
        result = platform.extract_keywords("我想买意外险")
        assert result == ["意外"]

    def test_dedup(self, platform: _MockPlatform):
        """去重：'医疗险和百万医疗' 只返回一个 '医疗'"""
        result = platform.extract_keywords("医疗险和百万医疗")
        assert result.count("医疗") == 1

    def test_order_preserved(self, platform: _MockPlatform):
        """保序：先出现的排前面"""
        result = platform.extract_keywords("先买意外险再买重疾险")
        assert result.index("意外") < result.index("重疾")

    def test_new_keywords_dingqi(self, platform: _MockPlatform):
        """新增：'定期寿险' → ['定期寿险']"""
        result = platform.extract_keywords("我想了解定期寿险")
        assert "定期寿险" in result

    def test_new_keywords_zhongshen(self, platform: _MockPlatform):
        """新增：'终身寿险' → ['终身寿险']"""
        result = platform.extract_keywords("终身寿险哪个好")
        assert "终身寿险" in result

    def test_new_keywords_yanglaoxian(self, platform: _MockPlatform):
        """新增：'养老险' → ['养老']"""
        result = platform.extract_keywords("养老险推荐")
        assert "养老" in result

    def test_new_keywords_jiaoyujin(self, platform: _MockPlatform):
        """新增：'教育金' → ['教育金']"""
        result = platform.extract_keywords("给孩子买教育金")
        # 正则第一层先匹配 "教育金"，第二层匹配 "孩子" 人群
        assert "教育金" in result

    def test_new_keywords_dabing(self, platform: _MockPlatform):
        """新增口语：'大病险' → ['重疾']"""
        result = platform.extract_keywords("大病险哪个好")
        assert "重疾" in result

    def test_new_keywords_ertong(self, platform: _MockPlatform):
        """新增：'儿童保险' → ['少儿']"""
        result = platform.extract_keywords("儿童保险怎么买")
        assert "少儿" in result

    def test_mixed_type_and_audience(self, platform: _MockPlatform):
        """混合：'给宝宝买重疾险' → 先有 '重疾'（正则），再有人群推断的"""
        result = platform.extract_keywords("给宝宝买重疾险")
        assert result[0] == "重疾"
        # 人群推断补充少儿相关
        assert any("少儿" in kw for kw in result)


# ======================================================================
# extract_keyword 兼容性测试
# ======================================================================

class TestExtractKeywordCompat:
    """旧 extract_keyword() 接口兼容性"""

    def test_returns_first(self, platform: _MockPlatform):
        """返回第一个关键词"""
        result = platform.extract_keyword("重疾险+意外险")
        assert result == "重疾"

    def test_fallback_to_bao_xian(self, platform: _MockPlatform):
        """空输入兜底返回 '保险' — 但实际 extract_keywords 不会返回空"""
        # extract_keywords 有兜底逻辑，所以 extract_keyword 不太会返回 "保险"
        # 这里验证它不会崩溃
        result = platform.extract_keyword("")
        assert isinstance(result, str)
        assert len(result) > 0


# ======================================================================
# _extract_audience_keywords 测试
# ======================================================================

class TestAudienceKeywords:
    """人群/场景推断测试"""

    def test_baby(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("给宝宝买保险")
        assert "少儿医疗" in result
        assert "少儿重疾" in result
        assert "少儿意外" in result

    def test_elderly(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("给老人买保险")
        assert "医疗" in result
        assert "防癌" in result
        assert "意外" in result

    def test_family(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("全家保障计划")
        assert "医疗" in result
        assert "意外" in result
        assert "重疾" in result

    def test_parents(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("给父母买保险")
        assert "医疗" in result
        assert "防癌" in result

    def test_hospital(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("住院怎么办")
        assert result == ["医疗"]

    def test_pension(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("养老规划")
        assert "年金" in result
        assert "养老" in result

    def test_education(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("教育储备")
        assert "教育金" in result

    def test_sudden_death(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("猝死风险")
        assert "意外" in result
        assert "寿险" in result

    def test_no_audience(self, platform: _MockPlatform):
        result = platform._extract_audience_keywords("普通问题")
        assert result == []

    def test_multiple_audiences(self, platform: _MockPlatform):
        """多个人群同时出现，结果去重"""
        result = platform._extract_audience_keywords("给宝宝和老人买保险")
        # 应包含少儿和老人相关的关键词，且去重
        assert "少儿医疗" in result
        assert "医疗" in result  # 老人的医疗
        # 检查不重复
        assert len(result) == len(set(result))


# ======================================================================
# _extract_age 测试
# ======================================================================

class TestExtractAge:
    """年龄提取测试"""

    def test_normal_age(self, platform: _MockPlatform):
        assert platform._extract_age("我28岁") == 28

    def test_child_age(self, platform: _MockPlatform):
        assert platform._extract_age("孩子3岁") == 3

    def test_elderly_age(self, platform: _MockPlatform):
        assert platform._extract_age("65岁老人") == 65

    def test_age_with_space(self, platform: _MockPlatform):
        assert platform._extract_age("我 30 岁") == 30

    def test_no_age(self, platform: _MockPlatform):
        assert platform._extract_age("我想买保险") is None

    def test_invalid_age(self, platform: _MockPlatform):
        """超出 0-150 范围的数字不作为年龄"""
        assert platform._extract_age("999岁") is None

    def test_zero_age(self, platform: _MockPlatform):
        assert platform._extract_age("0岁新生儿") == 0


# ======================================================================
# _fallback_keywords 测试
# ======================================================================

class TestFallbackKeywords:
    """兜底策略测试"""

    # 预算分层
    def test_budget_low(self, platform: _MockPlatform):
        """预算 ≤500 → ['意外', '医疗']"""
        result = platform._fallback_keywords("预算300")
        assert result == ["意外", "医疗"]

    def test_budget_500(self, platform: _MockPlatform):
        """预算正好 500 → ['意外', '医疗']"""
        result = platform._fallback_keywords("预算500元")
        assert result == ["意外", "医疗"]

    def test_budget_mid(self, platform: _MockPlatform):
        """预算 501-3000 → ['医疗', '意外', '重疾']"""
        result = platform._fallback_keywords("预算2000")
        assert result == ["医疗", "意外", "重疾"]

    def test_budget_3000(self, platform: _MockPlatform):
        """预算正好 3000 → ['医疗', '意外', '重疾']"""
        result = platform._fallback_keywords("预算3000")
        assert result == ["医疗", "意外", "重疾"]

    def test_budget_high(self, platform: _MockPlatform):
        """预算 >3000 → ['重疾', '医疗', '寿险']"""
        result = platform._fallback_keywords("预算5000")
        assert result == ["重疾", "医疗", "寿险"]

    # 年龄分层
    def test_age_child(self, platform: _MockPlatform):
        """年龄 <18 → ['少儿医疗', '少儿意外']"""
        result = platform._fallback_keywords("5岁")
        assert result == ["少儿医疗", "少儿意外"]

    def test_age_17(self, platform: _MockPlatform):
        """年龄 17（仍 <18） → ['少儿医疗', '少儿意外']"""
        result = platform._fallback_keywords("17岁")
        assert result == ["少儿医疗", "少儿意外"]

    def test_age_adult(self, platform: _MockPlatform):
        """年龄 18-54 → ['医疗', '重疾', '意外']"""
        result = platform._fallback_keywords("30岁")
        assert result == ["医疗", "重疾", "意外"]

    def test_age_55(self, platform: _MockPlatform):
        """年龄 ≥55 → ['医疗', '防癌']"""
        result = platform._fallback_keywords("55岁")
        assert result == ["医疗", "防癌"]

    def test_age_elderly(self, platform: _MockPlatform):
        """年龄 70 → ['医疗', '防癌']"""
        result = platform._fallback_keywords("70岁")
        assert result == ["医疗", "防癌"]

    # 预算优先于年龄
    def test_budget_over_age(self, platform: _MockPlatform):
        """同时有预算和年龄时，预算优先"""
        result = platform._fallback_keywords("5岁预算500")
        assert result == ["意外", "医疗"]  # 按预算分层

    # 通用兜底
    def test_no_info(self, platform: _MockPlatform):
        """无预算无年龄 → ['医疗', '重疾', '意外']"""
        result = platform._fallback_keywords("我想了解下保险")
        assert result == ["医疗", "重疾", "意外"]

    def test_empty_input(self, platform: _MockPlatform):
        """空输入 → ['医疗', '重疾', '意外']"""
        result = platform._fallback_keywords("")
        assert result == ["医疗", "重疾", "意外"]


# ======================================================================
# _extract_budget_simple 测试
# ======================================================================

class TestExtractBudgetSimple:
    """简单预算提取函数测试"""

    def test_budget_prefix(self):
        assert _extract_budget_simple("预算1000元") == 1000.0

    def test_yuan_per_year(self):
        assert _extract_budget_simple("2000元/年") == 2000.0

    def test_nian_yusuan(self):
        assert _extract_budget_simple("年预算3000") == 3000.0

    def test_yuan_zuoyou(self):
        assert _extract_budget_simple("500元左右") == 500.0

    def test_yuan_yinei(self):
        assert _extract_budget_simple("1000元以内") == 1000.0

    def test_no_budget(self):
        assert _extract_budget_simple("我想买保险") is None

    def test_zero_not_matched(self):
        """预算为 0 不匹配"""
        assert _extract_budget_simple("预算0元") is None


# ======================================================================
# KEYWORD_MAPPING 覆盖测试
# ======================================================================

class TestKeywordMapping:
    """确保新增的关键词映射覆盖了更多口语表达"""

    @pytest.mark.parametrize("input_word,expected", [
        ("少儿险", "少儿"),
        ("儿童保险", "少儿"),
        ("养老险", "养老"),
        ("养老保险", "养老"),
        ("教育金", "教育金"),
        ("定期寿险", "定期寿险"),
        ("终身寿险", "终身寿险"),
        ("大病险", "重疾"),
        ("大病保险", "重疾"),
        ("意外伤害", "意外"),
        ("防癌医疗", "防癌"),
    ])
    def test_mapping_exists(self, input_word: str, expected: str):
        assert KEYWORD_MAPPING.get(input_word) == expected


# ======================================================================
# INSURANCE_TYPE_RE 覆盖测试
# ======================================================================

class TestInsuranceTypeRegex:
    """确保正则能匹配新增的险种"""

    @pytest.mark.parametrize("text,expected_match", [
        ("我要买百万医疗险", "百万医疗险"),
        ("定期寿险推荐", "定期寿险"),
        ("终身寿险", "终身寿险"),
        ("养老险怎么样", "养老险"),
        ("教育金保险", "教育金保险"),
        ("大病险", "大病险"),
        ("防癌医疗险", "防癌医疗险"),
        ("儿童保险", "儿童保险"),
        ("少儿险", "少儿险"),
        ("旅游险怎么买", "旅游险"),
    ])
    def test_regex_matches(self, text: str, expected_match: str):
        matches = INSURANCE_TYPE_RE.findall(text)
        assert expected_match in matches
