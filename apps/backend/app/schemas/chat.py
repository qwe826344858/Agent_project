"""聊天相关的 Pydantic 数据模型"""

from typing import Optional

from pydantic import BaseModel, Field


# ========== 请求模型 ==========

class ChatRequest(BaseModel):
    """POST /api/chat 请求体"""
    message: str = Field(..., min_length=1, description="用户问题")
    session_id: Optional[str] = Field(None, alias="sessionId", description="会话ID")
    request_id: Optional[str] = Field(None, alias="requestId", description="请求追踪ID")


# ========== 响应模型 ==========

class SuggestionsResponse(BaseModel):
    """GET /api/suggestions 响应"""
    suggestions: list[str]


class HealthResponse(BaseModel):
    """GET /api/healthz 响应"""
    status: str = "ok"
    service: str = "backend"
    time: str


# ========== SSE 事件载荷 ==========

class SSEStatusPayload(BaseModel):
    stage: str
    message: str


class SSEDeltaPayload(BaseModel):
    text: str


class SourceItem(BaseModel):
    title: str
    url: str
    site: str


class SSESourcesPayload(BaseModel):
    items: list[SourceItem]


class SSEDisclaimerPayload(BaseModel):
    text: str


class SSEDonePayload(BaseModel):
    request_id: str = Field(..., alias="requestId")

    model_config = {"populate_by_name": True}


class SSEErrorPayload(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = Field(None, alias="requestId")

    model_config = {"populate_by_name": True}


# ========== 意图识别模型 ==========

class IntentResult(BaseModel):
    """意图识别输出"""
    intent: str
    needs_followup: bool = False
    missing_slots: list[str] = []
    reason: str = ""


# ========== 搜索词生成模型 ==========

class QueryResult(BaseModel):
    """搜索词生成输出"""
    queries: list[str]


# ========== 搜索结果模型 ==========

class SearchResultItem(BaseModel):
    """单条搜索结果"""
    title: str
    url: str
    site: str
    snippet: str


# ========== 回答生成模型 ==========

class AnswerResult(BaseModel):
    """回答生成输出"""
    summary: str
    details: list[str] = []
    caution: Optional[str] = None


# ========== 产品推荐卡片（双通道方案） ==========

class ProductCard(BaseModel):
    """产品推荐卡片 — 由代码逻辑生成，不经过 LLM"""
    id: str                          # 唯一标识（用于 products_update 匹配）
    name: str                        # 产品名称
    company: str = ""                # 保险公司
    price: Optional[str] = None      # 价格（如 "258元/年起"）
    price_label: str = "加载中"       # 价格展示文案
    tags: list[str] = []             # 标签（如 ["百万医疗", "保证续保"]）
    url: str                         # 投保链接（保险平台商品详情页）
    platform: str                    # 来源平台名称
    brief: str = ""                  # 一句话简介


class SSEProductsPayload(BaseModel):
    """SSE products 事件载荷"""
    items: list[ProductCard]


class SSEProductsUpdatePayload(BaseModel):
    """SSE products_update 事件载荷"""
    items: list[ProductCard]
