"""网页采集 -> 清洗 -> 切块 -> embedding -> pgvector 入库"""

import logging
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from app.core.config import settings
from app.services.embedding_client import embedding_client
from app.services.html_cleaner import clean_html
from app.services.pgvector_store import ChunkRecord, pgvector_store
from app.services.text_chunker import TextChunker
from app.services.webpage_fetcher import webpage_fetcher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    """单条 URL 的入库结果"""

    url: str
    status: str
    document_id: int | None = None
    chunk_count: int = 0
    message: str = ""


class WebpageIngestionService:
    """面向手动触发脚本的网页入库服务。"""

    def __init__(self) -> None:
        self.chunker = TextChunker(
            chunk_size=settings.INGEST_CHUNK_SIZE,
            overlap=settings.INGEST_CHUNK_OVERLAP,
        )

    async def ingest_urls(
        self,
        urls: list[str],
        namespace: str | None = None,
        source_type: str = "web_page",
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[IngestionResult]:
        pgvector_store.ensure_schema()
        namespace = namespace or settings.INGEST_NAMESPACE
        results: list[IngestionResult] = []

        for url in self._deduplicate(urls):
            result = await self.ingest_url(
                url=url,
                namespace=namespace,
                source_type=source_type,
                extra_metadata=extra_metadata or {},
            )
            results.append(result)

        return results

    async def ingest_url(
        self,
        url: str,
        namespace: str,
        source_type: str,
        extra_metadata: dict[str, Any],
    ) -> IngestionResult:
        raw_html = await webpage_fetcher.fetch(url)
        if not raw_html:
            return IngestionResult(url=url, status="failed", message="抓取失败")

        cleaned_text, cn_count = clean_html(raw_html)
        if cn_count < settings.INGEST_MIN_CN_CHARS:
            return IngestionResult(
                url=url,
                status="skipped",
                message=f"清洗后中文内容过少: {cn_count}",
            )

        title = self._extract_title(raw_html)
        chunks = self.chunker.split(cleaned_text)
        if not chunks:
            return IngestionResult(url=url, status="skipped", message="切块结果为空")

        embeddings = await embedding_client.embed_texts([chunk.text for chunk in chunks])
        chunk_records = [
            ChunkRecord(
                chunk_index=chunk.index,
                content=chunk.text,
                embedding=embeddings[idx],
                metadata={
                    "namespace": namespace,
                    "source_url": url,
                    "source_type": source_type,
                    "title": title,
                    "chunk_index": chunk.index,
                    "start_offset": chunk.start_offset,
                    "end_offset": chunk.end_offset,
                    **extra_metadata,
                },
            )
            for idx, chunk in enumerate(chunks)
        ]

        document_id = pgvector_store.upsert_document_with_chunks(
            namespace=namespace,
            source_type=source_type,
            source_url=url,
            title=title,
            raw_html=raw_html,
            cleaned_text=cleaned_text,
            metadata={
                "namespace": namespace,
                "source_type": source_type,
                "cn_count": cn_count,
                "title": title,
                **extra_metadata,
            },
            chunks=chunk_records,
        )

        return IngestionResult(
            url=url,
            status="success",
            document_id=document_id,
            chunk_count=len(chunk_records),
            message=f"入库成功: {len(chunk_records)} chunks",
        )

    @staticmethod
    def _extract_title(raw_html: str) -> str:
        soup = BeautifulSoup(raw_html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        return title[:200]

    @staticmethod
    def _deduplicate(urls: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for url in urls:
            clean = url.strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            result.append(clean)
        return result


webpage_ingestion_service = WebpageIngestionService()
