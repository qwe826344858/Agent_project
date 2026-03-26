"""LLM 服务单元测试 —— 通过 Mock LLMClient 避免真实 API 调用"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.chat import AnswerResult, SearchResultItem


# ============================================================
# IntentService 测试
# ============================================================


class TestIntentService:
    """意图识别服务测试"""

    @pytest.mark.asyncio
    async def test_intent_knowledge_explain(self):
        """输入知识类问题，验证返回 intent == 'knowledge_explain'"""
        mock_response = {
            "intent": "knowledge_explain",
            "needs_followup": False,
            "missing_slots": [],
            "reason": "知识类问题",
        }

        with patch("app.services.intent_service.llm_client") as mock_llm:
            mock_llm.call_json = AsyncMock(return_value=mock_response)

            # 延迟导入，确保 patch 生效
            from app.services.intent_service import IntentService

            service = IntentService()
            result = await service.classify("什么是免赔额")

        assert result.intent == "knowledge_explain"
        assert result.needs_followup is False
        assert result.missing_slots == []
        assert result.reason == "知识类问题"

    @pytest.mark.asyncio
    async def test_intent_recommendation_with_followup(self):
        """输入推荐类问题，验证 needs_followup == True 且包含缺失槽位"""
        mock_response = {
            "intent": "product_recommendation",
            "needs_followup": True,
            "missing_slots": ["age", "budget"],
            "reason": "缺少关键信息",
        }

        with patch("app.services.intent_service.llm_client") as mock_llm:
            mock_llm.call_json = AsyncMock(return_value=mock_response)

            from app.services.intent_service import IntentService

            service = IntentService()
            result = await service.classify("推荐个保险")

        assert result.intent == "product_recommendation"
        assert result.needs_followup is True
        # _apply_followup_rules 会对 missing_slots 取交集并排序
        # age 和 budget 都在规则的 required_slots 中，所以保留
        assert "age" in result.missing_slots
        assert "budget" in result.missing_slots

    @pytest.mark.asyncio
    async def test_intent_out_of_scope(self):
        """输入非保险领域问题，验证 intent == 'out_of_scope'"""
        mock_response = {
            "intent": "out_of_scope",
            "needs_followup": False,
            "missing_slots": [],
            "reason": "非保险领域问题",
        }

        with patch("app.services.intent_service.llm_client") as mock_llm:
            mock_llm.call_json = AsyncMock(return_value=mock_response)

            from app.services.intent_service import IntentService

            service = IntentService()
            result = await service.classify("今天天气怎么样")

        assert result.intent == "out_of_scope"
        assert result.needs_followup is False


# ============================================================
# QueryService 测试
# ============================================================


class TestQueryService:
    """搜索词生成服务测试"""

    @pytest.mark.asyncio
    async def test_query_generates_keywords(self):
        """验证返回的关键词列表长度在 3-5 之间"""
        mock_response = {
            "queries": ["重疾险 2026", "重疾险推荐", "热门重疾险"],
        }

        with patch("app.services.query_service.llm_client") as mock_llm:
            mock_llm.call_json = AsyncMock(return_value=mock_response)

            from app.services.query_service import QueryService

            service = QueryService()
            result = await service.generate("推荐一款重疾险", "product_recommendation")

        assert isinstance(result, list)
        assert 3 <= len(result) <= 5

    @pytest.mark.asyncio
    async def test_query_injects_year(self):
        """对 product_recommendation 意图，验证返回的关键词中包含当前年份"""
        current_year = str(datetime.now().year)
        # 故意不在任何关键词中包含年份，让 _inject_year 自动注入
        mock_response = {
            "queries": ["重疾险推荐", "热门重疾险", "重疾险排行"],
        }

        with patch("app.services.query_service.llm_client") as mock_llm:
            mock_llm.call_json = AsyncMock(return_value=mock_response)

            from app.services.query_service import QueryService

            service = QueryService()
            result = await service.generate("推荐一款重疾险", "product_recommendation")

        # 至少有一个关键词包含当前年份
        has_year = any(current_year in q for q in result)
        assert has_year, f"关键词列表中未包含当前年份 {current_year}: {result}"


# ============================================================
# AnswerService 测试
# ============================================================


class TestAnswerService:
    """回答生成服务测试"""

    @pytest.mark.asyncio
    async def test_answer_generates_result(self):
        """Mock LLM call_text 返回 JSON 结构的回答，验证返回 AnswerResult 有 summary"""
        mock_answer = json.dumps(
            {
                "summary": "免赔额是指保险合同中规定的保险公司不予赔付的金额部分。",
                "details": [
                    "免赔额分为绝对免赔额和相对免赔额两种类型。",
                    "一般医疗险的免赔额为 1 万元。",
                ],
                "caution": "具体免赔额以保险合同条款为准。",
            },
            ensure_ascii=False,
        )

        search_results = [
            SearchResultItem(
                title="什么是免赔额",
                url="https://example.com/deductible",
                site="example.com",
                snippet="免赔额是保险合同中规定的一定金额...",
            ),
        ]

        with patch("app.services.answer_service.llm_client") as mock_llm:
            mock_llm.call_text = AsyncMock(return_value=mock_answer)

            from app.services.answer_service import AnswerService

            service = AnswerService()
            result = await service.generate(
                message="什么是免赔额",
                intent="knowledge_explain",
                search_results=search_results,
            )

        assert isinstance(result, AnswerResult)
        assert result.summary != ""
        assert "免赔额" in result.summary
        assert len(result.details) > 0
        assert result.caution is not None

    @pytest.mark.asyncio
    async def test_answer_followup(self):
        """Mock LLM call_text 返回追问话术，验证返回非空字符串"""
        mock_followup = "您好！为了更好地为您推荐保险产品，请问您今年多大了？另外，您的预算大概在什么范围呢？"

        with patch("app.services.answer_service.llm_client") as mock_llm:
            mock_llm.call_text = AsyncMock(return_value=mock_followup)

            from app.services.answer_service import AnswerService

            service = AnswerService()
            result = await service.generate_followup(
                message="推荐个保险",
                missing_slots=["age", "budget"],
            )

        assert isinstance(result, str)
        assert len(result) > 0
