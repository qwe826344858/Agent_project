"""家庭场景检测 + 预算分摊 单元测试"""

import pytest

# 直接导入待测函数
from app.services.platform_apis import _detect_family_size, _extract_budget


class TestDetectFamilySize:
    """家庭人数检测"""

    def test_explicit_family_size(self):
        assert _detect_family_size("我们一家4口想买保险") == 4

    def test_family_with_children_count(self):
        # "两个孩子" → 2 + 2(夫妻) = 4
        assert _detect_family_size("全家人都配上保险，两个孩子一个5岁一个8岁") == 4

    def test_single_child(self):
        # "1个孩子" → 1 + 2 = 3
        assert _detect_family_size("全家保险规划，1个孩子") == 3

    def test_family_keyword_no_count(self):
        # 有家庭关键词但无明确人数 → 默认 3
        assert _detect_family_size("想给全家买保险") == 3

    def test_not_family_scenario(self):
        # 不是家庭场景 → 返回 1（不分摊）
        assert _detect_family_size("我想给自己买一份医疗险") == 1

    def test_baby_scenario_not_family(self):
        # "宝宝"场景但不含"全家/家庭" → 不分摊
        assert _detect_family_size("给宝宝买一份保险") == 1

    def test_three_children(self):
        assert _detect_family_size("家庭保险规划，3个小孩") == 5  # 3 + 2


class TestBudgetExtraction:
    """预算提取回归 — 确保"万"单位正确处理"""

    def test_wan_unit(self):
        assert _extract_budget("全家预算一年1万块") == 10000

    def test_normal_budget(self):
        assert _extract_budget("预算每年5000左右") == 5000

    def test_500_budget(self):
        result = _extract_budget("预算一年不超过500块")
        assert result == 500

    def test_no_budget(self):
        assert _extract_budget("想了解下保险是什么") is None


class TestFamilyBudgetIntegration:
    """家庭预算分摊集成测试（逻辑模拟）"""

    def test_family_budget_split(self):
        """全家1万预算，4口人 → 人均2500"""
        user_input = "我们家条件还可以，想给全家人都配上保险，两个孩子一个5岁一个8岁，全家预算一年1万块"
        budget = _extract_budget(user_input)
        family_size = _detect_family_size(user_input)
        per_person = budget / family_size

        assert budget == 10000
        assert family_size == 4
        assert per_person == 2500

    def test_single_person_no_split(self):
        """非家庭场景不分摊"""
        user_input = "我今年38岁，预算每年5000左右"
        budget = _extract_budget(user_input)
        family_size = _detect_family_size(user_input)

        assert budget == 5000
        assert family_size == 1
