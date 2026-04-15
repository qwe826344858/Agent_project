"""PostgreSQL + pgvector 入库服务"""

import json
import logging
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import psycopg

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkRecord:
    """待写入的 chunk 记录"""

    chunk_index: int
    content: str
    embedding: list[float]
    metadata: dict[str, Any]


class PgVectorStore:
    """使用 PostgreSQL 存正文与 chunk，并用 pgvector 存 embedding。"""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or settings.DATABASE_URL

    def ensure_schema(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                except psycopg.Error as exc:
                    raise RuntimeError(
                        "当前 PostgreSQL 未安装 pgvector 扩展，"
                        "请先在现有数据库环境中安装后再执行入库脚本。"
                    ) from exc
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rag_documents (
                        id BIGSERIAL PRIMARY KEY,
                        namespace TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        source_url TEXT NOT NULL,
                        title TEXT NOT NULL DEFAULT '',
                        raw_html TEXT NOT NULL DEFAULT '',
                        cleaned_text TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE(namespace, source_url)
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                        id BIGSERIAL PRIMARY KEY,
                        document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        embedding vector NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE(document_id, chunk_index)
                    );
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rag_documents_namespace ON rag_documents(namespace);"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_id ON rag_chunks(document_id);"
                )
            conn.commit()

    def upsert_document_with_chunks(
        self,
        namespace: str,
        source_type: str,
        source_url: str,
        title: str,
        raw_html: str,
        cleaned_text: str,
        metadata: dict[str, Any],
        chunks: list[ChunkRecord],
    ) -> int:
        if not chunks:
            raise ValueError("chunks 不能为空")

        content_hash = sha256(cleaned_text.encode("utf-8")).hexdigest()

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rag_documents (
                        namespace, source_type, source_url, title,
                        raw_html, cleaned_text, content_hash, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (namespace, source_url)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        raw_html = EXCLUDED.raw_html,
                        cleaned_text = EXCLUDED.cleaned_text,
                        content_hash = EXCLUDED.content_hash,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id;
                    """,
                    (
                        namespace,
                        source_type,
                        source_url,
                        title,
                        raw_html,
                        cleaned_text,
                        content_hash,
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
                document_id = cur.fetchone()[0]
                cur.execute("DELETE FROM rag_chunks WHERE document_id = %s;", (document_id,))

                for chunk in chunks:
                    cur.execute(
                        """
                        INSERT INTO rag_chunks (
                            document_id, chunk_index, content, content_hash, embedding, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb);
                        """,
                        (
                            document_id,
                            chunk.chunk_index,
                            chunk.content,
                            sha256(chunk.content.encode("utf-8")).hexdigest(),
                            self._to_vector_literal(chunk.embedding),
                            json.dumps(chunk.metadata, ensure_ascii=False),
                        ),
                    )
            conn.commit()

        logger.info(
            "RAG 入库完成: namespace=%s, url=%s, document_id=%s, chunks=%d",
            namespace,
            source_url[:120],
            document_id,
            len(chunks),
        )
        return document_id

    @staticmethod
    def _to_vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{value:.12g}" for value in values) + "]"


pgvector_store = PgVectorStore()
