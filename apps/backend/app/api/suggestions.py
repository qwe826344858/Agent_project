"""推荐问题接口"""

from fastapi import APIRouter

from app.schemas.chat import SuggestionsResponse

router = APIRouter()

# 保险相关推荐问题（当前阶段硬编码，后续可改为从配置或数据库读取）
_SUGGESTIONS: list[str] = [
    "重疾险和医疗险有什么区别？",
    "百万医疗险怎么选？",
    "什么是免赔额？",
    "意外险通常保哪些场景？",
    "等待期是什么意思？",
]


@router.get("/suggestions", response_model=SuggestionsResponse)
async def suggestions() -> SuggestionsResponse:
    """返回保险相关推荐问题列表"""
    return SuggestionsResponse(suggestions=_SUGGESTIONS)
