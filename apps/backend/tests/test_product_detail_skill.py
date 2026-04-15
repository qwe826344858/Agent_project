"""ProductDetailSkill 单元测试 — 校验逻辑、JSON 解析"""

import pytest

from app.schemas.chat import DutyItem
from app.services.product_detail_skill import (
    ProductDetailSkill,
    validate_extraction,
)


class TestValidateExtraction:
    """字符回查校验"""

    def test_all_matched(self):
        """所有保障项在原文中都能找到 → 通过"""
        duties = [
            DutyItem(name="一般医疗及外购药械费用医疗保险金", coverage="300万"),
            DutyItem(name="重大疾病医疗保险金", coverage="300万"),
        ]
        text = "本产品包含一般医疗及外购药械费用医疗保险金300万和重大疾病医疗保险金300万"
        passed, rate, reason = validate_extraction(duties, text)
        assert passed is True
        assert rate == 1.0

    def test_partial_match_above_threshold(self):
        """3/4 = 75% ≥ 70% → 通过"""
        duties = [
            DutyItem(name="一般医疗保险金", coverage="300万"),
            DutyItem(name="重大疾病保险金", coverage="300万"),
            DutyItem(name="恶性肿瘤先进疗法", coverage="600万"),
            DutyItem(name="完全不存在的保障", coverage="100万"),
        ]
        text = "本产品包含一般医疗保险金和重大疾病保险金以及恶性肿瘤先进疗法"
        passed, rate, reason = validate_extraction(duties, text)
        assert passed is True  # 3/4 = 75%
        assert rate >= 0.7

    def test_below_threshold(self):
        """匹配率 < 70% → 不通过"""
        duties = [
            DutyItem(name="幻觉保障A", coverage="100万"),
            DutyItem(name="幻觉保障B", coverage="200万"),
            DutyItem(name="一般医疗", coverage="300万"),
        ]
        text = "本产品包含一般医疗保障"
        passed, rate, reason = validate_extraction(duties, text)
        # "幻觉保障A"、"幻觉保障B" 在 text 中都找不到
        assert passed is False

    def test_empty_duties(self):
        """空列表 → 不通过"""
        passed, rate, reason = validate_extraction([], "some text")
        assert passed is False
        assert rate == 0.0

    def test_generic_name_full_match(self):
        """名称全是通用词时用完整名称匹配"""
        duties = [DutyItem(name="医疗费用保险金", coverage="100万")]
        text = "本产品包含医疗费用保险金"
        passed, rate, reason = validate_extraction(duties, text)
        assert passed is True


class TestParseDutiesJson:
    """JSON 解析"""

    def setup_method(self):
        self.skill = ProductDetailSkill()

    def test_normal_json(self):
        raw = '''{"product_name": "测试", "duties": [{"name": "一般医疗", "coverage": "300万", "description": "desc", "is_optional": false}]}'''
        duties = self.skill._parse_duties_json(raw)
        assert len(duties) == 1
        assert duties[0].name == "一般医疗"
        assert duties[0].coverage == "300万"
        assert duties[0].is_optional is False

    def test_json_with_markdown_wrapper(self):
        """LLM 可能返回 ```json ... ``` 包裹"""
        raw = '```json\n{"duties": [{"name": "重疾保障", "coverage": "500万"}]}\n```'
        duties = self.skill._parse_duties_json(raw)
        assert len(duties) == 1
        assert duties[0].name == "重疾保障"

    def test_empty_duties(self):
        raw = '{"duties": []}'
        duties = self.skill._parse_duties_json(raw)
        assert duties == []

    def test_invalid_json(self):
        duties = self.skill._parse_duties_json("这不是 JSON")
        assert duties == []

    def test_skip_empty_name(self):
        """name 为空的项应被跳过"""
        raw = '{"duties": [{"name": "", "coverage": "100万"}, {"name": "有效项", "coverage": "200万"}]}'
        duties = self.skill._parse_duties_json(raw)
        assert len(duties) == 1
        assert duties[0].name == "有效项"

    def test_description_truncate(self):
        """description 超过 200 字时截断"""
        long_desc = "a" * 300
        raw = f'{{"duties": [{{"name": "测试", "description": "{long_desc}"}}]}}'
        duties = self.skill._parse_duties_json(raw)
        assert len(duties[0].description) <= 200


class TestExtractProductName:
    """产品名称提取"""

    def setup_method(self):
        self.skill = ProductDetailSkill()

    def test_extract_name(self):
        raw = '{"product_name": "众安尊享e生2025", "duties": []}'
        assert self.skill._extract_product_name(raw) == "众安尊享e生2025"

    def test_no_name(self):
        raw = '{"duties": []}'
        assert self.skill._extract_product_name(raw) == ""

    def test_invalid_json(self):
        assert self.skill._extract_product_name("not json") == ""
