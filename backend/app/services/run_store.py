from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from ..schemas import AnalysisRequest, RunRecord


class RunStore:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create(self, run_id: str, request: AnalysisRequest) -> RunRecord:
        now = datetime.now(UTC)
        record = RunRecord(
            run_id=run_id,
            status="queued",
            created_at=now,
            updated_at=now,
            source_id=request.source_id,
            output_label=request.output_label,
            controls=request.controls,
        )
        self.save(record)
        return record

    def save(self, record: RunRecord) -> RunRecord:
        run_dir = self.runs_dir / record.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = record.model_dump(mode="json")
        with self._lock:
            with (run_dir / "run.json").open("w", encoding="utf-8") as file_handle:
                json.dump(payload, file_handle, indent=2)
        return record

    def load(self, run_id: str) -> RunRecord | None:
        run_path = self.runs_dir / run_id / "run.json"
        if not run_path.exists():
            return None
        with run_path.open("r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
        return RunRecord.model_validate(payload)

    def list(self) -> list[RunRecord]:
        records: list[RunRecord] = []
        for run_file in sorted(self.runs_dir.glob("*/run.json"), reverse=True):
            with run_file.open("r", encoding="utf-8") as file_handle:
                records.append(RunRecord.model_validate(json.load(file_handle)))
        return sorted(records, key=lambda item: item.created_at, reverse=True)

