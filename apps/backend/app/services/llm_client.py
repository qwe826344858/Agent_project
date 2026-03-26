"""LLM 统一调用封装，基于 LiteLLM

支持多 Provider 同时加载，按业务阶段路由到不同模型：
  - get_client("intent")  → 意图识别阶段配置的模型
  - get_client("answer")  → 回答生成阶段配置的模型
  - get_client()          → 默认模型

路由策略由 app/config/llm_providers.yaml 的 routing 段控制。
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import litellm

from app.core.config import settings
from app.core.errors import UpstreamError, UpstreamTimeoutError
from app.core.llm_providers import ProviderConfig, registry

logger = logging.getLogger("smartinsure.llm")

litellm.suppress_debug_info = True


class LLMClient:
    """多端点自动切换的 LLM 调用客户端

    支持同一个 Provider 配置多个端点（如 Anthropic 协议 + OpenAI 协议），
    第一个端点超时/失败时自动 fallback 到下一个端点。
    """

    def __init__(self, provider_config: ProviderConfig) -> None:
        self.provider_name: str = provider_config.name
        self.model: str = provider_config.litellm_model
        self.api_key: str = provider_config.api_key
        self.api_base: str = provider_config.api_base
        self.timeout: int = settings.LLM_TIMEOUT
        self.max_retries: int = settings.LLM_MAX_RETRIES

        # 从 litellm_model 中解析协议（prefix 部分）
        protocol = self.model.split("/")[0] if "/" in self.model else "unknown"
        model_name = self.model.split("/", 1)[1] if "/" in self.model else self.model
        key_hint = f"***{self.api_key[-4:]}" if len(self.api_key) > 4 else "(未配置)"

        logger.info(
            "========================================\n"
            "  LLM 服务初始化\n"
            "  Provider:  %s\n"
            "  协议:      %s\n"
            "  模型:      %s\n"
            "  API Base:  %s\n"
            "  API Key:   %s\n"
            "  超时:      %ds / 重试: %d次\n"
            "========================================",
            self.provider_name, protocol, model_name,
            self.api_base, key_hint, self.timeout, self.max_retries,
        )

    def __repr__(self) -> str:
        return f"LLMClient(provider={self.provider_name}, model={self.model})"

    # ------------------------------------------------------------------
    # 内部：多端点 fallback 调用
    # ------------------------------------------------------------------

    async def _completion(
        self,
        messages: list[dict],
        temperature: float,
        timeout: int,
        stream: bool = False,
    ):
        """带重试的底层调用"""
        last_exc: Exception | None = None

        for attempt in range(1 + self.max_retries):
            try:
                response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    timeout=timeout,
                    stream=stream,
                )
                return response

            except (asyncio.TimeoutError, litellm.exceptions.Timeout) as exc:
                last_exc = exc
                logger.warning(
                    "[%s] LLM 调用超时 (attempt=%d/%d)",
                    self.provider_name, attempt + 1, 1 + self.max_retries,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "[%s] LLM 调用异常: %s (attempt=%d/%d)",
                    self.provider_name, exc, attempt + 1, 1 + self.max_retries,
                )

            if attempt < self.max_retries:
                delay = 2 ** attempt
                logger.info("[%s] 等待 %ds 后重试…", self.provider_name, delay)
                await asyncio.sleep(delay)

        if isinstance(last_exc, (asyncio.TimeoutError, litellm.exceptions.Timeout)):
            raise UpstreamTimeoutError(
                f"[{self.provider_name}] LLM 调用超时（已重试 {self.max_retries} 次）"
            )
        raise UpstreamError(f"[{self.provider_name}] LLM 调用失败: {last_exc}")

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def call_json(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        timeout: int | None = None,
    ) -> dict:
        """调用 LLM 并返回 JSON 解析后的结果"""
        timeout = timeout or self.timeout

        for json_attempt in range(2):
            response = await self._completion(
                messages=messages, temperature=temperature, timeout=timeout,
            )
            content: str = response.choices[0].message.content.strip()

            # 去除 markdown 代码块
            if content.startswith("```"):
                lines = content.splitlines()
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                if json_attempt == 0:
                    logger.warning(
                        "[%s] JSON 解析失败，重试: %s",
                        self.provider_name, content[:200],
                    )
                    continue
                raise UpstreamError(
                    f"[{self.provider_name}] LLM 返回无法解析为 JSON: {content[:200]}"
                )

        raise UpstreamError(f"[{self.provider_name}] call_json 意外退出")  # pragma: no cover

    async def call_text(
        self,
        messages: list[dict],
        temperature: float = 0.4,
        timeout: int | None = None,
    ) -> str:
        """调用 LLM 并返回文本结果（自动过滤 <think> 思维链内容）"""
        timeout = timeout or self.timeout
        response = await self._completion(
            messages=messages, temperature=temperature, timeout=timeout,
        )
        content = response.choices[0].message.content.strip()
        # 过滤 <think>...</think> 块
        import re as _re
        content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()
        return content

    async def call_text_stream(
        self,
        messages: list[dict],
        temperature: float = 0.4,
        timeout: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式调用 LLM，逐块返回文本（自动过滤 <think> 思维链内容）"""
        timeout = timeout or self.timeout
        response = await self._completion(
            messages=messages, temperature=temperature, timeout=timeout, stream=True,
        )
        in_think = False  # 是否在 <think> 标签内
        buffer = ""       # 缓冲区（处理跨 chunk 的标签边界）

        async for chunk in response:
            delta = chunk.choices[0].delta
            if not delta or not delta.content:
                continue

            text = delta.content

            # 处理 <think> 标签过滤
            if in_think:
                # 在 think 块内，查找 </think>
                end_idx = text.find("</think>")
                if end_idx != -1:
                    in_think = False
                    text = text[end_idx + len("</think>"):]
                else:
                    continue  # 整个 chunk 都在 think 内，跳过

            # 检查是否进入 <think>
            start_idx = text.find("<think>")
            if start_idx != -1:
                # 输出 <think> 之前的内容
                before = text[:start_idx]
                if before:
                    yield before
                # 查找同一 chunk 内是否有 </think>
                end_idx = text.find("</think>", start_idx)
                if end_idx != -1:
                    # 同一 chunk 内闭合了
                    after = text[end_idx + len("</think>"):]
                    if after:
                        yield after
                else:
                    in_think = True
                continue

            if text:
                yield text


# ======================================================================
# 客户端池 — 按 provider 名称缓存实例
# ======================================================================

_client_pool: dict[str, LLMClient] = {}


def get_client(stage: str | None = None) -> LLMClient:
    """获取指定业务阶段的 LLMClient

    参数:
        stage: 业务阶段名（intent / query / answer / followup）
               为 None 时返回默认 provider 的客户端

    路由逻辑由 llm_providers.yaml 的 routing 段控制。
    客户端按 provider 名称缓存，相同 provider 共享同一个实例。
    """
    if stage:
        provider_cfg = registry.get_for_stage(stage)
    else:
        provider_cfg = registry.get_default()
        if provider_cfg is None:
            raise UpstreamError("无可用的默认 LLM Provider，请检查配置")

    cache_key = provider_cfg.name
    if cache_key not in _client_pool:
        _client_pool[cache_key] = LLMClient(provider_cfg)
        logger.info("创建 LLMClient: %s", _client_pool[cache_key])

    return _client_pool[cache_key]


# 向后兼容：llm_client 作为默认客户端的快捷引用
# 已有的 service 代码 `from app.services.llm_client import llm_client` 无需改动
llm_client = get_client()
