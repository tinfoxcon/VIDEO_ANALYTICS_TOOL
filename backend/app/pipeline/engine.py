from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .detection import HybridMaritimeDetector
from .preprocessing import enhance_frame, simulate_disturbance
from .runtime import load_runtime_modules
from .tracker import SimpleMultiObjectTracker
from .visualization import compose_visualization_frame


@dataclass(slots=True)
class PipelineResult:
    summary: dict[str, Any]
    artifacts: dict[str, str]
    alerts: list[dict[str, Any]]
    latest_tracks: list[dict[str, Any]]
    timeline: list[dict[str, Any]]


class VideoAnalyticsPipeline:
    def __init__(self, device_preference: str = "auto") -> None:
        self._modules = load_runtime_modules()
        self.cv2 = self._modules["cv2"]
        self.detector = HybridMaritimeDetector(device_preference=device_preference)

    def run(
        self,
        input_video: Path,
        run_dir: Path,
        controls: Any,
        progress_callback: Callable[[float], None] | None = None,
    ) -> PipelineResult:
        if not input_video.exists():
            raise FileNotFoundError(f"Input video does not exist: {input_video}")

        capture = self.cv2.VideoCapture(str(input_video))
        if not capture.isOpened():
            raise RuntimeError(f"Unable to open video: {input_video}")

        source_fps = capture.get(self.cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(capture.get(self.cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(self.cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(capture.get(self.cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        output_width = width * 2 if controls.comparison_view else width
        output_height = height + 72

        run_dir.mkdir(parents=True, exist_ok=True)
        source_copy = run_dir / "digitized-input.mp4"
        if source_copy.resolve() != input_video.resolve():
            shutil.copy2(input_video, source_copy)

        output_video = run_dir / "annotated-output.mp4"
        preview_image = run_dir / "preview-frame.jpg"
        timeline_path = run_dir / "timeline.json"
        writer = self.cv2.VideoWriter(
            str(output_video),
            self.cv2.VideoWriter_fourcc(*"mp4v"),
            source_fps,
            (output_width, output_height),
        )

        tracker = SimpleMultiObjectTracker(max_track_age=controls.max_track_age)
        timeline: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        previous_enhanced = None
        total_detections = 0
        processed_frames = 0
        preview_written = False
        start_time = time.perf_counter()

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                disturbed_frame = simulate_disturbance(
                    frame=frame,
                    profile=controls.disturbance_profile,
                    cv2=self.cv2,
                    np=self._modules["numpy"],
                )
                enhanced_frame, diagnostics = enhance_frame(
                    frame=disturbed_frame,
                    controls=controls,
                    cv2=self.cv2,
                    np=self._modules["numpy"],
                    previous_frame=previous_enhanced,
                )
                previous_enhanced = enhanced_frame.copy()

                detections = self.detector.detect(
                    frame=enhanced_frame,
                    controls=controls,
                    frame_index=processed_frames,
                )
                total_detections += len(detections)
                tracks, frame_alerts = tracker.update(
                    detections=detections,
                    frame_shape=enhanced_frame.shape,
                    alert_area_ratio=controls.alert_area_ratio,
                )

                elapsed_seconds = processed_frames / max(source_fps, 1.0)
                visualized_frame = compose_visualization_frame(
                    original_frame=disturbed_frame,
                    enhanced_frame=enhanced_frame,
                    tracks=tracks,
                    frame_index=processed_frames,
                    elapsed_seconds=elapsed_seconds,
                    controls=controls,
                    diagnostics=diagnostics,
                    cv2=self.cv2,
                )
                writer.write(visualized_frame)

                if not preview_written:
                    self.cv2.imwrite(str(preview_image), visualized_frame)
                    preview_written = True

                alert_entries = [
                    {
                        "frame_index": processed_frames,
                        "timestamp_seconds": elapsed_seconds,
                        "track_id": alert["track_id"],
                        "severity": alert["severity"],
                        "message": alert["message"],
                    }
                    for alert in frame_alerts
                ]
                alerts.extend(alert_entries)

                if processed_frames % max(1, int(source_fps // 2) or 1) == 0:
                    timeline.append(
                        {
                            "frame_index": processed_frames,
                            "timestamp_seconds": elapsed_seconds,
                            "track_count": len(tracks),
                            "tracks": [self._serialize_track(track, elapsed_seconds) for track in tracks],
                            "alerts": alert_entries,
                        }
                    )

                processed_frames += 1
                if progress_callback and frame_count:
                    progress_callback(min(processed_frames / frame_count, 0.99))
        finally:
            capture.release()
            writer.release()

        total_time = max(time.perf_counter() - start_time, 0.001)
        with timeline_path.open("w", encoding="utf-8") as file_handle:
            json.dump(timeline, file_handle, indent=2)

        result = PipelineResult(
            summary={
                "frames_processed": processed_frames,
                "video_fps": round(source_fps, 2),
                "processed_fps": round(processed_frames / total_time, 2),
                "total_detections": total_detections,
                "unique_tracks": tracker.unique_track_count,
                "active_alerts": len([track for track in tracker._tracks if track.alert_state != "steady"]),
                "disturbance_profile": controls.disturbance_profile,
                "device": self.detector.device,
                "notes": [
                    "Hybrid pipeline combines PyTorch boat detection with OpenCV motion cues.",
                    "Input panel shows disturbed footage, output panel shows filtered/tracked result.",
                    "Alert state is based on track persistence and apparent target growth in frame.",
                ],
            },
            artifacts={
                "input_video": f"/media/outputs/runs/{run_dir.name}/{source_copy.name}",
                "output_video": f"/media/outputs/runs/{run_dir.name}/{output_video.name}",
                "preview_image": f"/media/outputs/runs/{run_dir.name}/{preview_image.name}",
                "timeline_json": f"/media/outputs/runs/{run_dir.name}/{timeline_path.name}",
            },
            alerts=alerts,
            latest_tracks=[self._serialize_track(track, processed_frames / max(source_fps, 1.0)) for track in tracker._tracks],
            timeline=timeline,
        )
        return result

    @staticmethod
    def _serialize_track(track: Any, elapsed_seconds: float) -> dict[str, Any]:
        return {
            "track_id": track.track_id,
            "label": track.label,
            "confidence": round(track.confidence, 3),
            "bbox": list(track.bbox),
            "age": track.age,
            "misses": track.misses,
            "source": track.source,
            "alert_state": track.alert_state,
            "last_seen_seconds": round(elapsed_seconds, 2),
        }

