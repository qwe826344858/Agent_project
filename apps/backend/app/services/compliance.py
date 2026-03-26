"""LLM 输出合规校验器 —— 检查并修复违规表达

保险领域 LLM 输出必须遵循合规要求，不得包含绝对化承诺、
夸大宣传、诱导购买等违规表达。本模块提供违规检测与自动修复能力。
"""

from __future__ import annotations


class ComplianceValidator:
    """LLM 输出合规校验器 — 检查是否包含违规表达"""

    # 禁用表达词库（参考 Prompt设计.md）
    PROHIBITED_PHRASES: list[str] = [
        "保证收益",
        "稳赚不赔",
        "100%赔付",
        "百分百赔付",
        "什么都保",
        "这款一定最好",
        "绝对最好",
        "肯定能赔",
        "必须买",
        "不买就亏",
        "限时",
        "抢购",
    ]

    # 违规词 → 温和替换映射表；未列出的违规词将被直接移除
    _REPLACEMENT_MAP: dict[str, str] = {
        "保证收益": "预期收益（具体以合同为准）",
        "稳赚不赔": "具有一定保障（具体以合同条款为准）",
        "100%赔付": "按合同约定赔付",
        "百分百赔付": "按合同约定赔付",
        "什么都保": "保障范围较广（具体以合同为准）",
        "这款一定最好": "这款产品具有一定优势",
        "绝对最好": "这款产品具有一定优势",
        "肯定能赔": "符合条款约定的情况下可理赔",
    }

    def validate(self, text: str) -> tuple[bool, list[str]]:
        """
        校验文本是否合规。

        返回 (is_compliant, violations)：
        - 合规时返回 (True, [])
        - 不合规时返回 (False, [违规词列表])
        """
        violations: list[str] = [
            phrase for phrase in self.PROHIBITED_PHRASES if phrase in text
        ]
        if violations:
            return False, violations
        return True, []

    def sanitize(self, text: str) -> str:
        """
        对不合规文本进行修复 — 将违规词替换为温和表达。

        替换策略：
        1. 有对应温和表达的违规词 → 替换为温和表达
        2. 没有映射的违规词 → 直接移除
        """
        result = text
        for phrase in self.PROHIBITED_PHRASES:
            if phrase in result:
                replacement = self._REPLACEMENT_MAP.get(phrase, "")
                result = result.replace(phrase, replacement)
        return result


# 导出全局实例
compliance_validator = ComplianceValidator()
