"""应用配置管理，通过环境变量注入

LLM 厂商的 API Key / Base URL 等配置由 YAML 配置文件 + 环境变量共同管理，
详见 app/config/llm_providers.yaml 和 app/core/llm_providers.py。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局配置"""

    # 基础
    APP_ENV: str = "development"
    LOG_LEVEL: str = "info"

    # ======================================================================
    # LLM — 通用入口（厂商专属配置见 app/config/llm_providers.yaml）
    # ======================================================================
    LLM_PROVIDER: str = "minimax"  # minimax/openai/deepseek/qwen/zhipu/moonshot/custom
    LLM_MODEL: str = ""            # 为空时使用 provider 默认模型
    LLM_API_KEY: str = ""          # 通用 Key（优先级高于 provider 专属 env）
    LLM_API_BASE: str = ""         # 通用 Base URL（优先级高于 provider 专属 env）
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 1

    # ======================================================================
    # 搜索
    # ======================================================================
    SEARCH_API_KEY: str = ""
    SEARCH_API_URL: str = "https://api.search.example.com/v1/search"
    SEARCH_TIMEOUT: int = 15
    SEARCH_TOP_N: int = 10

    # Open-WebSearch MCP（免费，无需 API Key，支持 Baidu/Bing 等多引擎）
    MCP_SEARCH_URL: str = "http://web-search:3000"  # Docker 网络内通过容器名访问
    MCP_SEARCH_ENGINES: str = "baidu,bing"  # 逗号分隔的搜索引擎列表

    # 编排
    ORCHESTRATOR: str = "lite"  # lite | langgraph

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Postgres
    DATABASE_URL: str = ""

    # ======================================================================
    # Embedding / RAG Ingestion
    # ======================================================================
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_BASE: str = ""
    EMBEDDING_TIMEOUT: int = 30
    EMBEDDING_BATCH_SIZE: int = 16

    INGEST_NAMESPACE: str = "default"
    INGEST_CHUNK_SIZE: int = 1200
    INGEST_CHUNK_OVERLAP: int = 200
    INGEST_MIN_CN_CHARS: int = 50

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
