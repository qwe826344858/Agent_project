"""文本切块服务测试"""

from app.services.text_chunker import TextChunker


class TestTextChunker:
    def test_split_paragraphs_with_overlap(self):
        chunker = TextChunker(chunk_size=20, overlap=5)
        text = "第一段内容很多很多很多\n\n第二段内容也很多很多很多\n\n第三段结束"

        chunks = chunker.split(text)

        assert len(chunks) >= 2
        assert chunks[0].text
        assert chunks[0].start_offset == 0
        assert chunks[1].start_offset < chunks[0].end_offset

    def test_split_empty_text(self):
        chunker = TextChunker(chunk_size=50, overlap=10)
        assert chunker.split("") == []

    def test_split_long_paragraph(self):
        chunker = TextChunker(chunk_size=10, overlap=2)
        text = "测" * 24

        chunks = chunker.split(text)

        assert len(chunks) == 3
        assert all(len(chunk.text) <= 10 for chunk in chunks)
