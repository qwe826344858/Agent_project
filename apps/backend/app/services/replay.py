"""失败样例回放框架

记录 LLM 调用失败案例到 JSON 文件，支持归档、检索和回放验证，
用于评估 Prompt 优化效果。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from app.services.llm_client import llm_client

logger = logging.getLogger("smartinsure.replay")

# 当前 Prompt 版本，随 Prompt 迭代手动更新
PROMPT_VERSION = "v1.0"


class ReplayRecorder:
    """失败样例记录器 — 将 LLM 调用失败案例写入 JSON 文件"""

    def __init__(self, replay_dir: str = "data/replay_cases"):
        self.replay_dir = Path(replay_dir)
        self.replay_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        case_id: str,
        stage: str,
        input_message: str,
        prompt_messages: list[dict],
        raw_output: str,
        expected: str | None = None,
        error: str | None = None,
        tags: list[str] | None = None,
    ) -> Path:
        """记录一条失败案例到 JSON 文件。

        文件名格式：{stage}_{case_id}_{timestamp}.json
        返回文件路径。
        """
        now = datetime.now()
        timestamp = now.strftime("%Y%m%dT%H%M%S")

        case_data = {
            "case_id": case_id,
            "stage": stage,
            "input_message": input_message,
            "prompt_messages": prompt_messages,
            "raw_output": raw_output,
            "expected": expected,
            "error": error,
            "tags": tags or [],
            "recorded_at": now.isoformat(timespec="seconds"),
            "prompt_version": PROMPT_VERSION,
        }

        file_name = f"{stage}_{case_id}_{timestamp}.json"
        file_path = self.replay_dir / file_name

        file_path.write_text(
            json.dumps(case_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("已记录失败案例: %s -> %s", case_id, file_path)
        return file_path

    def list_cases(self, stage: str | None = None) -> list[dict]:
        """列出已记录的失败案例，可按 stage 过滤"""
        cases: list[dict] = []

        for fp in sorted(self.replay_dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("跳过无法读取的案例文件 %s: %s", fp, exc)
                continue

            if stage is not None and data.get("stage") != stage:
                continue

            # 附带文件路径，方便后续加载
            data["_file"] = str(fp)
            cases.append(data)

        return cases

    def load_case(self, file_path: str) -> dict:
        """加载单个失败案例"""
        path = Path(file_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_file"] = str(path)
        return data


class ReplayRunner:
    """失败样例回放器 — 加载历史案例并重新执行 LLM 调用，对比结果"""

    def __init__(self, recorder: ReplayRecorder | None = None):
        self.recorder = recorder or replay_recorder

    async def replay(self, case: dict) -> dict:
        """重放单个案例。

        1. 使用案例中保存的 prompt_messages 重新调用 LLM
        2. 对比新旧输出
        3. 返回 {"case_id", "stage", "original_output", "new_output", "improved": bool}
        """
        stage = case["stage"]
        prompt_messages = case["prompt_messages"]
        original_output = case["raw_output"]
        expected = case.get("expected")

        # 根据 stage 选择调用模式：intent / query 需要 JSON，answer 需要文本
        if stage in ("intent", "query"):
            result = await llm_client.call_json(prompt_messages)
            new_output = json.dumps(result, ensure_ascii=False)
        else:
            new_output = await llm_client.call_text(prompt_messages)

        # 判定是否改善：如果有 expected 字段，检查新输出是否包含期望内容
        if expected:
            improved = expected.lower() in new_output.lower()
        else:
            # 没有 expected 时，只要新输出与原输出不同即视为"有变化"
            improved = new_output.strip() != original_output.strip()

        return {
            "case_id": case["case_id"],
            "stage": stage,
            "original_output": original_output,
            "new_output": new_output,
            "improved": improved,
        }

    async def replay_all(self, stage: str | None = None) -> list[dict]:
        """批量回放所有案例"""
        cases = self.recorder.list_cases(stage=stage)
        results: list[dict] = []

        for case in cases:
            try:
                result = await self.replay(case)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                logger.error("回放案例 %s 失败: %s", case.get("case_id"), exc)
                results.append(
                    {
                        "case_id": case.get("case_id"),
                        "stage": case.get("stage"),
                        "original_output": case.get("raw_output"),
                        "new_output": None,
                        "improved": False,
                        "error": str(exc),
                    }
                )

        return results


# 全局单例，供各模块直接导入使用
replay_recorder = ReplayRecorder()
