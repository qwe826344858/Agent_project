"""OpenAI 兼容 Embedding 客户端"""

import logging

import httpx

from app.core.config import settings
from app.core.llm_providers import registry

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """调用 OpenAI 兼容 `/embeddings` 接口。"""

    def __init__(self) -> None:
        provider = registry.get_default()
        self.api_key = settings.EMBEDDING_API_KEY or (provider.api_key if provider else "")
        self.api_base = settings.EMBEDDING_API_BASE or (provider.api_base if provider else "")
        self.model = settings.EMBEDDING_MODEL
        self.timeout = settings.EMBEDDING_TIMEOUT
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_base:
            raise ValueError("EMBEDDING_API_BASE 未配置，且无法从默认 provider 回退")
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY 未配置，且无法从默认 provider 回退")

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            payload = {
                "model": self.model,
                "input": batch,
            }
            response = await self._post_embeddings(payload)
            data = response.get("data", [])
            if len(data) != len(batch):
                raise ValueError("embedding 返回数量与输入数量不一致")
            vectors.extend(item["embedding"] for item in data)
        return vectors

    async def _post_embeddings(self, payload: dict) -> dict:
        url = f"{self.api_base.rstrip('/')}/embeddings"
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=8.0)) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            logger.info("embedding 请求成功: model=%s, count=%d", self.model, len(payload["input"]))
            return response.json()


embedding_client = EmbeddingClient()
