"""数据模型 v2 扩展测试 — ChatRequest 新字段 + DutyItem / ProductDetail"""

import pytest
from app.schemas.chat import (
    ChatRequest,
    DutyItem,
    ProductDetail,
    SSEDetailItemsPayload,
)


# ---------- ChatRequest 扩展 ----------

class TestChatRequestWithAction:
    """test_chat_request_with_action：含 action/productUrl/productName 的请求"""

    def test_all_new_fields(self):
        req = ChatRequest(
            message="查看产品详情",
            sessionId="s1",
            requestId="r1",
            action="product_detail",
            productUrl="https://example.com/product/123",
            productName="好医保长期医疗险",
        )
        assert req.action == "product_detail"
        assert req.product_url == "https://example.com/product/123"
        assert req.product_name == "好医保长期医疗险"

    def test_alias_field_access(self):
        """确保 alias 字段既能通过别名传入，也能用 Python 属性名访问"""
        req = ChatRequest(
            message="详情",
            productUrl="https://a.com",
            productName="测试产品",
        )
        assert req.product_url == "https://a.com"
        assert req.product_name == "测试产品"


class TestChatRequestBackwardCompatible:
    """test_chat_request_backward_compatible：不传新字段时正常工作"""

    def test_minimal_request(self):
        req = ChatRequest(message="你好")
        assert req.message == "你好"
        assert req.action is None
        assert req.product_url is None
        assert req.product_name is None

    def test_old_fields_only(self):
        req = ChatRequest(
            message="推荐一款医疗险",
            sessionId="sess-001",
            requestId="req-001",
        )
        assert req.session_id == "sess-001"
        assert req.request_id == "req-001"
        assert req.action is None


# ---------- DutyItem ----------

class TestDutyItemConstruction:
    """test_duty_item_construction：DutyItem 构造和默认值"""

    def test_minimal(self):
        item = DutyItem(name="一般医疗")
        assert item.name == "一般医疗"
        assert item.coverage == ""
        assert item.description == ""
        assert item.is_optional is False

    def test_full(self):
        item = DutyItem(
            name="质子重离子",
            coverage="100万",
            description="确诊恶性肿瘤后的质子重离子治疗费用",
            is_optional=True,
        )
        assert item.name == "质子重离子"
        assert item.coverage == "100万"
        assert item.is_optional is True


# ---------- ProductDetail ----------

class TestProductDetailConstruction:
    """test_product_detail_construction：ProductDetail 构造和 duties 列表"""

    def test_minimal(self):
        detail = ProductDetail(
            product_name="好医保",
            product_url="https://example.com/product",
        )
        assert detail.product_name == "好医保"
        assert detail.product_url == "https://example.com/product"
        assert detail.platform == ""
        assert detail.duties == []
        assert detail.cn_char_count == 0
        assert detail.match_rate == 0.0

    def test_with_duties(self):
        duties = [
            DutyItem(name="一般医疗", coverage="300万"),
            DutyItem(name="重疾医疗", coverage="600万"),
            DutyItem(name="质子重离子", coverage="100万", is_optional=True),
        ]
        detail = ProductDetail(
            product_name="好医保长期医疗险",
            product_url="https://example.com/product/123",
            platform="小雨伞",
            duties=duties,
            cn_char_count=5200,
            match_rate=0.85,
        )
        assert len(detail.duties) == 3
        assert detail.duties[0].name == "一般医疗"
        assert detail.duties[2].is_optional is True
        assert detail.platform == "小雨伞"
        assert detail.cn_char_count == 5200
        assert detail.match_rate == 0.85


# ---------- SSEDetailItemsPayload ----------

class TestSSEDetailItemsPayload:
    """SSE detail_items 事件载荷序列化"""

    def test_serialization(self):
        payload = SSEDetailItemsPayload(
            product_name="测试产品",
            duties=[DutyItem(name="住院医疗", coverage="200万")],
        )
        data = payload.model_dump()
        assert data["product_name"] == "测试产品"
        assert len(data["duties"]) == 1
        assert data["duties"][0]["name"] == "住院医疗"
