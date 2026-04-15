"""产品详情查询技能 — 封装"抓取→清洗→LLM提取→校验→缓存→LLM翻译"完整链路

Agent 调用 Skill 模式：编排器识别 action=product_detail 后直接调用本 Skill，
Skill 内部编排两轮 LLM 调用，对外 yield SSE 事件字典。
"""

import json
import logging
import re
from collections.abc import AsyncGenerator

import httpx

from app.schemas.chat import DutyItem, ProductDetail
from app.services.html_cleaner import clean_html
from app.services.product_detail_cache import product_detail_cache
from app.services.prompts import (
    DETAIL_EXPLAIN_PROMPT_TEMPLATE,
    DETAIL_EXPLAIN_SYSTEM_PROMPT,
    DETAIL_EXTRACT_PROMPT_TEMPLATE,
    DETAIL_EXTRACT_SYSTEM_PROMPT,
    DETAIL_FOLLOWUP_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# LLM 客户端（延迟导入避免循环依赖）
try:
    from app.services.llm_client import llm_client
except ImportError:
    llm_client = None  # type: ignore[assignment]

# 校验时需要去除的通用词和连接词
_GENERIC_WORDS_RE = re.compile(r"(保险金|医疗保险|医疗|费用|责任|保障|保险|及|和|或|的)")


class ProductDetailSkill:
    """产品详情查询技能

    首次查询（缓存未命中）：
      yield status → detail_items → status → delta(流式) → done
    追问（缓存命中）：
      yield status → delta(流式) → done
    """

    async def run(
        self,
        product_url: str,
        product_name: str = "",
        user_question: str = "",
    ) -> AsyncGenerator[dict, None]:
        """执行产品详情查询，yield SSE 事件字典"""

        # ---- Step 1: 查缓存 ----
        cached = product_detail_cache.get(product_url)
        if cached:
            # 缓存命中：直接用结构化数据生成回答
            yield {"event": "status", "data": {"stage": "answering", "message": "正在生成保障解读..."}}
            async for chunk in self._generate_answer(cached, user_question):
                yield {"event": "delta", "data": {"text": chunk}}
            return

        # ---- Step 2: 抓取网页 ----
        yield {"event": "status", "data": {"stage": "reading", "message": "正在读取产品页面..."}}

        raw_html = await self._fetch_page(product_url)
        if not raw_html:
            yield {"event": "delta", "data": {"text": f"暂时无法访问该产品页面，建议直接查看：{product_url}"}}
            return

        # ---- Step 3: 清洗 ----
        cleaned_text, cn_count = clean_html(raw_html)
        logger.info("网页清洗: %d 中文字符, URL=%s", cn_count, product_url[:60])

        if cn_count < 50:
            yield {"event": "delta", "data": {"text": f"该页面内容较少，无法提取保障详情，建议直接查看：{product_url}"}}
            return

        # ---- Step 4: LLM 第 1 轮 — 结构化提取（带校验重试） ----
        yield {"event": "status", "data": {"stage": "analyzing", "message": "正在分析保障项目..."}}

        detail = await self._extract_with_retry(
            cleaned_text=cleaned_text,
            cn_count=cn_count,
            product_url=product_url,
            product_name=product_name,
            max_retries=3,
        )

        if not detail:
            yield {"event": "delta", "data": {"text": f"暂时无法自动解析此产品的保障详情，建议直接查看：{product_url}"}}
            return

        # 推送结构化数据
        yield {"event": "detail_items", "data": {
            "product_name": detail.product_name,
            "duties": [d.model_dump() for d in detail.duties],
        }}

        # 写入全局缓存
        product_detail_cache.set(product_url, detail)

        # ---- Step 5: LLM 第 2 轮 — 通俗化输出 ----
        yield {"event": "status", "data": {"stage": "answering", "message": "正在生成通俗解读..."}}

        async for chunk in self._generate_answer(detail, user_question):
            yield {"event": "delta", "data": {"text": chunk}}

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _fetch_page(self, url: str) -> str | None:
        """HTTP GET 抓取网页，返回 HTML 文本"""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
            ) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                })
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            logger.warning("网页抓取失败: %s — %s", url[:60], exc)
            return None

    async def _extract_with_retry(
        self,
        cleaned_text: str,
        cn_count: int,
        product_url: str,
        product_name: str,
        max_retries: int = 3,
    ) -> ProductDetail | None:
        """带校验重试的结构化提取"""
        if llm_client is None:
            logger.error("llm_client 未初始化，无法提取产品详情")
            return None

        for attempt in range(1, max_retries + 1):
            # 第 3 次尝试缩短输入
            input_text = cleaned_text[:3000] if attempt == 3 else cleaned_text

            # 构建提取 Prompt
            prompt = DETAIL_EXTRACT_PROMPT_TEMPLATE.format(cleaned_text=input_text)
            messages = [
                {"role": "system", "content": DETAIL_EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            # LLM 调用
            try:
                raw_result = await llm_client.call_text(messages, temperature=0.2)
            except Exception as exc:
                logger.warning("第 %d 次提取 LLM 调用失败: %s", attempt, exc)
                continue

            # 解析 JSON
            duties = self._parse_duties_json(raw_result)
            if not duties:
                logger.warning("第 %d 次提取: JSON 解析失败", attempt)
                continue

            # 提取产品名
            extracted_name = self._extract_product_name(raw_result) or product_name

            # 字符回查校验
            passed, match_rate, reason = validate_extraction(duties, cleaned_text)
            logger.info("第 %d 次提取: %s", attempt, reason)

            if passed:
                return ProductDetail(
                    product_name=extracted_name,
                    product_url=product_url,
                    duties=duties,
                    cn_char_count=cn_count,
                    match_rate=match_rate,
                )

        logger.warning("3 次提取均未通过校验: %s", product_url[:60])
        return None

    def _parse_duties_json(self, raw_text: str) -> list[DutyItem]:
        """从 LLM 输出中解析 JSON 格式的保障项列表"""
        # 尝试提取 JSON 块
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return []

        duties_raw = data.get("duties", [])
        if not isinstance(duties_raw, list):
            return []

        duties = []
        for item in duties_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            duties.append(DutyItem(
                name=name,
                coverage=str(item.get("coverage", "")),
                description=str(item.get("description", ""))[:200],
                is_optional=bool(item.get("is_optional", False)),
            ))

        return duties

    def _extract_product_name(self, raw_text: str) -> str:
        """从 LLM 返回的 JSON 中提取产品名称"""
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if not json_match:
            return ""
        try:
            data = json.loads(json_match.group())
            return str(data.get("product_name", ""))
        except (json.JSONDecodeError, AttributeError):
            return ""

    async def _generate_answer(
        self,
        detail: ProductDetail,
        user_question: str = "",
    ) -> AsyncGenerator[str, None]:
        """LLM 第 2 轮：基于结构化数据生成通俗回答（流式）"""
        if llm_client is None:
            yield "LLM 服务暂不可用，请稍后重试。"
            return

        # 格式化保障项文本
        duties_text = "\n".join(
            f"- {d.name}（{d.coverage}）{'【可选】' if d.is_optional else ''}: {d.description}"
            for d in detail.duties
        )

        # 选择 Prompt
        if user_question.strip():
            prompt = DETAIL_FOLLOWUP_PROMPT_TEMPLATE.format(
                product_name=detail.product_name,
                duties_formatted=duties_text,
                user_question=user_question,
            )
        else:
            prompt = DETAIL_EXPLAIN_PROMPT_TEMPLATE.format(
                product_name=detail.product_name,
                duties_formatted=duties_text,
            )

        messages = [
            {"role": "system", "content": DETAIL_EXPLAIN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            async for chunk in llm_client.call_text_stream(messages, temperature=0.4):
                yield chunk
        except Exception as exc:
            logger.warning("产品详情解读 LLM 失败: %s", exc)
            yield "抱歉，解读生成失败，请稍后重试。"


# ------------------------------------------------------------------
# 校验函数（模块级，方便单元测试调用）
# ------------------------------------------------------------------

def validate_extraction(
    duties: list[DutyItem],
    cleaned_text: str,
) -> tuple[bool, float, str]:
    """校验 LLM 提取结果的准确性 — 字符回查匹配

    策略：将保障项名称拆成连续 2-4 字的中文片段，
    检查这些片段在原文中的命中率。命中率 ≥ 70% 视为通过。

    Returns:
        (是否通过, 匹配率, 原因描述)
    """
    if not duties:
        return False, 0.0, "未提取到任何保障项"

    matched = 0
    for duty in duties:
        if _name_found_in_text(duty.name, cleaned_text):
            matched += 1

    match_rate = matched / len(duties)
    reason = f"匹配 {matched}/{len(duties)} 项 ({match_rate:.0%})"

    passed = match_rate >= 0.7
    return passed, match_rate, reason


def _name_found_in_text(name: str, text: str) -> bool:
    """检查保障项名称是否在原文中有据可查

    策略：
    1. 先尝试完整名称匹配
    2. 再提取名称中所有连续中文片段（≥2字），逐个检查
    3. 任一片段命中即视为"有据可查"
    """
    # 完整名称匹配
    if name in text:
        return True

    # 提取名称中的中文片段
    cn_segments = re.findall(r"[\u4e00-\u9fff]{2,}", name)
    if not cn_segments:
        return False

    # 逐个片段检查（跳过过于通用的短词）
    generic_short = {"保险", "医疗", "费用", "责任", "保障", "保险金", "医疗险"}
    for seg in cn_segments:
        if seg in generic_short:
            continue
        if seg in text:
            return True

    # 所有非通用片段都没命中，再试完整名称的前 4 个中文字符
    cn_chars = re.findall(r"[\u4e00-\u9fff]", name)
    if len(cn_chars) >= 4:
        prefix = "".join(cn_chars[:4])
        if prefix in text:
            return True

    return False
