"""失败样例回放框架测试"""

import json

import pytest

from app.services.replay import ReplayRecorder


# ---------- 辅助函数 ----------

def _make_recorder(tmp_path):
    """使用 tmp_path 创建 ReplayRecorder，避免污染项目目录"""
    return ReplayRecorder(replay_dir=str(tmp_path / "replay_cases"))


def _record_sample(recorder: ReplayRecorder, case_id: str, stage: str = "intent"):
    """快捷录入一条示例失败案例"""
    return recorder.record(
        case_id=case_id,
        stage=stage,
        input_message="推荐个保险",
        prompt_messages=[{"role": "user", "content": "推荐个保险"}],
        raw_output='{"intent": "knowledge_explain"}',
        expected="product_recommendation with followup",
        error="intent misclassified as knowledge_explain",
        tags=["误判", "推荐类"],
    )


# ---------- 测试用例 ----------

class TestReplayRecorder:
    """ReplayRecorder 单元测试"""

    def test_record_case(self, tmp_path):
        """记录一条案例后，JSON 文件应存在且内容正确"""
        recorder = _make_recorder(tmp_path)
        file_path = _record_sample(recorder, case_id="LLM-001")

        # 文件应存在
        assert file_path.exists()
        assert file_path.suffix == ".json"

        # 文件名应包含 stage 和 case_id
        assert "intent" in file_path.name
        assert "LLM-001" in file_path.name

        # 内容应包含所有关键字段
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["case_id"] == "LLM-001"
        assert data["stage"] == "intent"
        assert data["input_message"] == "推荐个保险"
        assert data["expected"] == "product_recommendation with followup"
        assert data["error"] == "intent misclassified as knowledge_explain"
        assert data["tags"] == ["误判", "推荐类"]
        assert "recorded_at" in data
        assert data["prompt_version"] == "v1.0"

    def test_list_cases(self, tmp_path):
        """记录多条案例后，list_cases 应返回正确数量"""
        recorder = _make_recorder(tmp_path)

        # 记录 3 条案例
        _record_sample(recorder, case_id="LLM-001", stage="intent")
        _record_sample(recorder, case_id="LLM-002", stage="query")
        _record_sample(recorder, case_id="LLM-003", stage="answer")

        cases = recorder.list_cases()
        assert len(cases) == 3

        # 每条案例应包含 _file 字段（文件路径）
        for case in cases:
            assert "_file" in case

    def test_list_cases_filter_stage(self, tmp_path):
        """按 stage 过滤应只返回匹配的案例"""
        recorder = _make_recorder(tmp_path)

        # 记录不同 stage 的案例
        _record_sample(recorder, case_id="LLM-001", stage="intent")
        _record_sample(recorder, case_id="LLM-002", stage="intent")
        _record_sample(recorder, case_id="LLM-003", stage="query")
        _record_sample(recorder, case_id="LLM-004", stage="answer")

        # 按 intent 过滤，应返回 2 条
        intent_cases = recorder.list_cases(stage="intent")
        assert len(intent_cases) == 2
        assert all(c["stage"] == "intent" for c in intent_cases)

        # 按 query 过滤，应返回 1 条
        query_cases = recorder.list_cases(stage="query")
        assert len(query_cases) == 1
        assert query_cases[0]["case_id"] == "LLM-003"

        # 按不存在的 stage 过滤，应返回空列表
        empty_cases = recorder.list_cases(stage="nonexistent")
        assert len(empty_cases) == 0

    def test_load_case(self, tmp_path):
        """load_case 应正确加载指定文件"""
        recorder = _make_recorder(tmp_path)
        file_path = _record_sample(recorder, case_id="LLM-010")

        loaded = recorder.load_case(str(file_path))
        assert loaded["case_id"] == "LLM-010"
        assert loaded["stage"] == "intent"
        assert "_file" in loaded
