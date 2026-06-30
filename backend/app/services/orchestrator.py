from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ..config import Settings
from ..pipeline.engine import VideoAnalyticsPipeline
from ..schemas import AlertEvent, AnalysisRequest, RunArtifacts, RunRecord, RunSummary, TrackSnapshot
from .demo_sources import resolve_source_path
from .run_store import RunStore


class AnalysisOrchestrator:
    def __init__(self, settings: Settings, store: RunStore) -> None:
        self.settings = settings
        self.store = store

    def queue_run(self, request: AnalysisRequest) -> RunRecord:
        resolve_source_path(
            settings=self.settings,
            source_id=request.source_id,
            explicit_path=request.source_path,
        )
        run_id = f"run-{uuid4().hex[:10]}"
        return self.store.create(run_id=run_id, request=request)

    def execute_run(self, run_id: str, request: AnalysisRequest) -> RunRecord:
        record = self.store.load(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")

        record.status = "running"
        record.updated_at = datetime.now(UTC)
        record.progress = 0.05
        self.store.save(record)

        def update_progress(progress: float) -> None:
            existing = self.store.load(run_id)
            if existing is None:
                return
            existing.progress = progress
            existing.updated_at = datetime.now(UTC)
            self.store.save(existing)

        try:
            source_path = resolve_source_path(
                settings=self.settings,
                source_id=request.source_id,
                explicit_path=request.source_path,
            )
            pipeline = VideoAnalyticsPipeline(device_preference=self.settings.default_device)
            result = pipeline.run(
                input_video=source_path,
                run_dir=self.settings.runs_dir / run_id,
                controls=request.controls,
                progress_callback=update_progress,
            )

            completed = self.store.load(run_id)
            if completed is None:
                raise KeyError(f"Run not found during completion: {run_id}")
            completed.status = "completed"
            completed.updated_at = datetime.now(UTC)
            completed.progress = 1.0
            completed.summary = RunSummary.model_validate(result.summary)
            completed.artifacts = RunArtifacts.model_validate(result.artifacts)
            completed.alerts = [AlertEvent.model_validate(alert) for alert in result.alerts]
            completed.latest_tracks = [TrackSnapshot.model_validate(track) for track in result.latest_tracks]
            return self.store.save(completed)
        except Exception as exc:  # noqa: BLE001 - bubble state to API consumers.
            failed = self.store.load(run_id)
            if failed is None:
                raise
            failed.status = "failed"
            failed.error = str(exc)
            failed.updated_at = datetime.now(UTC)
            return self.store.save(failed)
