"""LLM 多模型注册中心 — 启动时加载所有 provider，按业务阶段路由到不同模型

核心概念：
- ProviderConfig：单个服务商的连接配置（model/key/base）
- LLMRegistry：全局注册表，持有所有可用的 provider 配置
- get_client(stage)：根据业务阶段从路由表获取对应的 LLMClient

配置文件：app/config/llm_providers.yaml
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings

logger = logging.getLogger("smartinsure.llm_providers")

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "llm_providers.yaml"


@dataclass(frozen=True)
class EndpointConfig:
    """单个端点的连接配置"""
    name: str            # 端点名称（如 "国内站-Anthropic协议"）
    litellm_model: str   # LiteLLM 模型名（如 anthropic/MiniMax-M2.5）
    api_key: str
    api_base: str


@dataclass(frozen=True)
class ProviderConfig:
    """单个 provider 的连接配置（含多端点 fallback 支持）"""
    name: str
    description: str
    litellm_model: str   # 默认端点的模型名
    api_key: str
    api_base: str
    endpoints: list[EndpointConfig] = ()  # 多端点列表，按优先级排序

    def __post_init__(self):
        # frozen=True 下用 object.__setattr__ 设置 mutable default
        if not self.endpoints:
            object.__setattr__(self, 'endpoints', [])


class LLMRegistry:
    """全局 LLM 注册表 — 管理所有已加载的 provider 和路由策略"""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._routing: dict[str, str] = {}  # stage -> provider_name
        self._default_provider: str = ""
        self._load()

    # ------------------------------------------------------------------
    # 初始化：从 YAML 加载
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """从 YAML 配置文件加载所有 provider 和路由规则"""
        if not _CONFIG_PATH.exists():
            logger.error("LLM 配置文件不存在: %s", _CONFIG_PATH)
            return

        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        # 默认 provider
        self._default_provider = data.get("default_provider", "")

        # 加载路由表
        routing_raw = data.get("routing", {})
        for stage, route_cfg in routing_raw.items():
            if isinstance(route_cfg, dict):
                self._routing[stage] = route_cfg.get("provider", self._default_provider)
            elif isinstance(route_cfg, str):
                self._routing[stage] = route_cfg

        # 加载所有 provider
        providers_raw = data.get("providers", {})
        for name, prov in providers_raw.items():
            if not isinstance(prov, dict):
                continue
            if not prov.get("enabled", True):
                logger.info("跳过已禁用的 provider: %s", name)
                continue

            config = self._resolve_provider(name, prov)
            self._providers[name] = config

            key_status = "✓ 已配置" if config.api_key else "✗ 未配置"
            logger.info(
                "已加载 provider: %-12s model=%-30s key=%s",
                name, config.litellm_model, key_status,
            )

        logger.info(
            "LLM 注册表就绪: %d 个 provider, 默认=%s, 路由=%s",
            len(self._providers),
            self._default_provider,
            dict(self._routing),
        )

    def _resolve_provider(self, name: str, prov: dict) -> ProviderConfig:
        """解析单个 provider 的最终配置（支持多端点）"""
        api_key_env = prov.get("api_key_env", "")
        api_key = os.environ.get(api_key_env, "") if api_key_env else ""

        # 解析多端点列表
        endpoints: list[EndpointConfig] = []
        raw_endpoints = prov.get("endpoints", [])
        for ep in raw_endpoints:
            if not isinstance(ep, dict):
                continue
            ep_prefix = ep.get("prefix", "")
            ep_model = ep.get("default_model", "")
            ep_base = ep.get("api_base", "")
            ep_litellm = f"{ep_prefix}/{ep_model}" if ep_prefix and ep_model else ep_model
            endpoints.append(EndpointConfig(
                name=ep.get("name", ep_base),
                litellm_model=ep_litellm,
                api_key=api_key,
                api_base=ep_base,
            ))

        # 向后兼容：如果没有 endpoints 列表，从单端点字段构建
        prefix = prov.get("prefix", "")
        default_model = prov.get("default_model", "")
        api_base_env = prov.get("api_base_env", "")
        default_base = prov.get("default_base", "")

        litellm_model = f"{prefix}/{default_model}" if prefix and default_model else default_model
        api_base = os.environ.get(api_base_env, "") if api_base_env else ""
        if not api_base:
            api_base = default_base

        if not endpoints:
            endpoints = [EndpointConfig(
                name="default",
                litellm_model=litellm_model,
                api_key=api_key,
                api_base=api_base,
            )]

        if endpoints:
            logger.info(
                "  provider '%s' 端点: %s",
                name, [ep.name for ep in endpoints],
            )

        return ProviderConfig(
            name=name,
            description=prov.get("description", ""),
            litellm_model=endpoints[0].litellm_model if endpoints else litellm_model,
            api_key=api_key,
            api_base=endpoints[0].api_base if endpoints else api_base,
            endpoints=endpoints,
        )

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    @property
    def providers(self) -> dict[str, ProviderConfig]:
        """所有已加载的 provider"""
        return dict(self._providers)

    @property
    def available_providers(self) -> list[str]:
        """已配置 Key 的可用 provider 名称列表"""
        return [name for name, cfg in self._providers.items() if cfg.api_key]

    def get_provider(self, name: str) -> ProviderConfig | None:
        """按名称获取 provider 配置"""
        return self._providers.get(name)

    def get_default(self) -> ProviderConfig | None:
        """获取默认 provider"""
        return self._providers.get(self._default_provider)

    def get_for_stage(self, stage: str) -> ProviderConfig:
        """根据业务阶段获取路由的 provider 配置

        查找顺序：routing[stage] → default_provider → 第一个有 Key 的 provider
        """
        # 1. 从路由表查找
        provider_name = self._routing.get(stage, self._default_provider)

        # 2. 路由表中指定的 provider 存在且有 Key
        cfg = self._providers.get(provider_name)
        if cfg and cfg.api_key:
            return cfg

        # 3. 回退到默认 provider
        if provider_name != self._default_provider:
            cfg = self._providers.get(self._default_provider)
            if cfg and cfg.api_key:
                logger.warning(
                    "stage '%s' 路由的 '%s' 不可用，回退到默认 '%s'",
                    stage, provider_name, self._default_provider,
                )
                return cfg

        # 4. 回退到任意一个有 Key 的 provider
        for name, c in self._providers.items():
            if c.api_key:
                logger.warning(
                    "stage '%s' 回退到可用 provider '%s'", stage, name,
                )
                return c

        # 5. 无任何可用 provider，返回默认配置（Key 为空，调用时会报错）
        fallback = self._providers.get(self._default_provider)
        if fallback:
            return fallback
        return ProviderConfig(
            name="none", description="无可用 provider",
            litellm_model="", api_key="", api_base="",
        )

    def list_providers(self) -> list[dict[str, str]]:
        """列出所有 provider 状态（供 API 查询）"""
        result = []
        for name, cfg in self._providers.items():
            result.append({
                "name": name,
                "description": cfg.description,
                "model": cfg.litellm_model,
                "available": bool(cfg.api_key),
                "is_default": name == self._default_provider,
                "stages": [s for s, p in self._routing.items() if p == name],
            })
        return result


# 全局单例 — 启动时加载所有配置
registry = LLMRegistry()
