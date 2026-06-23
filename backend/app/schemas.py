from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


DisturbanceProfile = Literal["clear", "blurred", "hazy", "reflective", "mixed"]
RunStatus = Literal["queued", "running", "completed", "failed"]


class OperatorControls(BaseModel):
    confidence_threshold: float = Field(default=0.55, ge=0.1, le=0.99)
    detection_interval: int = Field(default=4, ge=1, le=30)
    max_track_age: int = Field(default=12, ge=1, le=120)
    min_box_area: int = Field(default=900, ge=64, le=100_000)
    process_scale: float = Field(default=0.8, ge=0.25, le=1.0)
    alert_area_ratio: float = Field(default=0.025, ge=0.001, le=0.5)
    motion_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    glare_suppression: float = Field(default=0.45, ge=0.0, le=1.0)
    sharpen_strength: float = Field(default=0.35, ge=0.0, le=2.0)
    temporal_smoothing: float = Field(default=0.2, ge=0.0, le=0.9)
    disturbance_profile: DisturbanceProfile = "mixed"
    enable_clahe: bool = True
    enable_glare_mask: bool = True
    enable_temporal_smoothing: bool = True
    comparison_view: bool = True


class AnalysisRequest(BaseModel):
    source_id: str = Field(default="mvtd-23-boat")
    source_path: str | None = None
    output_label: str = Field(default="maritime-poc", min_length=2, max_length=64)
    controls: OperatorControls = Field(default_factory=OperatorControls)


class AlertEvent(BaseModel):
    frame_index: int
    timestamp_seconds: float
    track_id: int
    severity: Literal["info", "warning", "critical"]
    message: str


class TrackSnapshot(BaseModel):
    track_id: int
    label: str
    confidence: float
    bbox: list[int]
    age: int
    misses: int
    source: str
    alert_state: str
    last_seen_seconds: float


class RunSummary(BaseModel):
    frames_processed: int
    video_fps: float
    processed_fps: float
    total_detections: int
    unique_tracks: int
    active_alerts: int
    disturbance_profile: DisturbanceProfile
    device: str
    notes: list[str]


class RunArtifacts(BaseModel):
    input_video: str
    output_video: str
    preview_image: str
    timeline_json: str


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    source_id: str
    output_label: str
    progress: float = 0.0
    controls: OperatorControls
    summary: RunSummary | None = None
    artifacts: RunArtifacts | None = None
    alerts: list[AlertEvent] = Field(default_factory=list)
    latest_tracks: list[TrackSnapshot] = Field(default_factory=list)
    error: str | None = None


class DemoSource(BaseModel):
    id: str
    title: str
    description: str
    source_page: str
    download_url: str
    local_path: str
    exists_locally: bool
    license_name: str
