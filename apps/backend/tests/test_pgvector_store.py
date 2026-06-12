"""pgvector store 纯函数测试"""

import pytest

pytest.importorskip("psycopg")

from app.services.pgvector_store import PgVectorStore


class TestPgVectorStore:
    def test_to_vector_literal(self):
        literal = PgVectorStore._to_vector_literal([0.1, 2.0, -3.25])
        assert literal == "[0.1,2,-3.25]"
