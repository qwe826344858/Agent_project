"""小雨伞保险公司名称提取 — 单元测试"""

import pytest

from app.services.platform_apis.xiaoyusan import _extract_company


@pytest.mark.parametrize(
    "product_name, expected",
    [
        ("众安保险众民保·百万医疗险2025", "众安保险"),
        ("中国人保金医保3号百万医疗险", "中国人保"),
        ("中英人寿爱守护C款重大疾病保险", "中英人寿"),
        ("复星联合星相守长期医疗险", "复星联合"),
        ("[税优版]某某产品", ""),
        # 补充：短名匹配
        ("众安百万医疗险", "众安"),
        ("平安e生保长期医疗险", "平安"),
        # 补充：优先匹配长名称
        ("人保财险大护甲5号意外险", "人保财险"),
        ("华贵人寿大麦旗舰版定期寿险", "华贵人寿"),
        # 补充：无匹配
        ("超级玛丽旗舰版重疾险", ""),
    ],
)
def test_extract_company(product_name: str, expected: str):
    """验证从产品名中正确提取保险公司名称"""
    assert _extract_company(product_name) == expected
