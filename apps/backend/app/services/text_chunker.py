"""文本切块服务"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """单个文本块"""

    index: int
    text: str
    start_offset: int
    end_offset: int


class TextChunker:
    """面向中文正文的轻量切块器"""

    def __init__(self, chunk_size: int = 1200, overlap: int = 200) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0:
            raise ValueError("overlap 不能小于 0")
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[TextChunk]:
        """按段落优先切块，必要时回退到定长切块。"""
        normalized = self._normalize(text)
        if not normalized:
            return []

        chunks: list[TextChunk] = []
        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]

        cursor = 0
        buffer = ""
        buffer_start = 0

        for paragraph in paragraphs:
            if len(paragraph) > self.chunk_size:
                if buffer:
                    chunks.append(
                        TextChunk(
                            index=len(chunks),
                            text=buffer,
                            start_offset=buffer_start,
                            end_offset=buffer_start + len(buffer),
                        )
                    )
                    cursor = buffer_start + max(len(buffer) - self.overlap, 0)
                    buffer = ""

                long_chunks = self._split_long_paragraph(
                    paragraph,
                    base_offset=cursor,
                    start_index=len(chunks),
                )
                chunks.extend(long_chunks)
                if long_chunks:
                    cursor = long_chunks[-1].end_offset - self.overlap
                continue

            candidate = paragraph if not buffer else f"{buffer}\n\n{paragraph}"
            if len(candidate) <= self.chunk_size:
                if not buffer:
                    buffer_start = cursor
                buffer = candidate
                continue

            chunks.append(
                TextChunk(
                    index=len(chunks),
                    text=buffer,
                    start_offset=buffer_start,
                    end_offset=buffer_start + len(buffer),
                )
            )
            cursor = buffer_start + max(len(buffer) - self.overlap, 0)
            buffer_start = cursor
            buffer = paragraph

        if buffer:
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    text=buffer,
                    start_offset=buffer_start,
                    end_offset=buffer_start + len(buffer),
                )
            )

        return chunks

    @staticmethod
    def _normalize(text: str) -> str:
        lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
        kept = [line for line in lines if line]
        return "\n\n".join(kept)

    def _split_long_paragraph(
        self,
        text: str,
        base_offset: int,
        start_index: int,
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        start = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    TextChunk(
                        index=start_index + len(chunks),
                        text=piece,
                        start_offset=base_offset + start,
                        end_offset=base_offset + start + len(piece),
                    )
                )
            if end >= len(text):
                break
            start = max(end - self.overlap, start + 1)

        return chunks
