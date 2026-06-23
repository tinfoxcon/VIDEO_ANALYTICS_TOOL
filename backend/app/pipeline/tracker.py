from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .detection import Detection


@dataclass(slots=True)
class TrackState:
    track_id: int
    bbox: tuple[int, int, int, int]
    label: str
    confidence: float
    source: str
    age: int = 0
    misses: int = 0
    hits: int = 1
    alert_state: str = "steady"
    history: list[tuple[int, int]] = field(default_factory=list)
    velocity: tuple[int, int] = (0, 0)

    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)


class SimpleMultiObjectTracker:
    def __init__(self, max_track_age: int, iou_threshold: float = 0.25, history_length: int = 32) -> None:
        self.max_track_age = max_track_age
        self.iou_threshold = iou_threshold
        self.history_length = history_length
        self._next_id = 1
        self._tracks: list[TrackState] = []
        self._seen_ids: set[int] = set()

    @property
    def unique_track_count(self) -> int:
        return len(self._seen_ids)

    def update(
        self,
        detections: list[Detection],
        frame_shape: tuple[int, int, int],
        alert_area_ratio: float,
    ) -> tuple[list[TrackState], list[dict[str, Any]]]:
        alerts: list[dict[str, Any]] = []
        unmatched_detections = detections.copy()
        matched_detection_indexes: set[int] = set()

        for track in self._tracks:
            prediction = self._predict_bbox(track)
            best_index = None
            best_iou = 0.0
            for index, detection in enumerate(unmatched_detections):
                if index in matched_detection_indexes:
                    continue
                score = self._iou(prediction, detection.bbox)
                if score > best_iou:
                    best_iou = score
                    best_index = index

            if best_index is None or best_iou < self.iou_threshold:
                track.age += 1
                track.misses += 1
                track.bbox = prediction
                continue

            detection = unmatched_detections[best_index]
            matched_detection_indexes.add(best_index)
            track.age += 1
            track.misses = 0
            track.hits += 1
            track.velocity = self._estimate_velocity(track.bbox, detection.bbox)
            track.bbox = detection.bbox
            track.label = detection.label
            track.confidence = detection.score
            track.source = detection.source
            track.history.append(track.center())
            track.history = track.history[-self.history_length :]
            track.alert_state = self._determine_alert_state(track, frame_shape, alert_area_ratio)
            if track.alert_state != "steady":
                alerts.append(
                    {
                        "track_id": track.track_id,
                        "severity": "critical" if track.alert_state == "critical" else "warning",
                        "message": f"Track {track.track_id} flagged as {track.alert_state}.",
                    }
                )

        for index, detection in enumerate(unmatched_detections):
            if index in matched_detection_indexes:
                continue
            new_track = TrackState(
                track_id=self._next_id,
                bbox=detection.bbox,
                label=detection.label,
                confidence=detection.score,
                source=detection.source,
                history=[self._bbox_center(detection.bbox)],
            )
            new_track.alert_state = self._determine_alert_state(new_track, frame_shape, alert_area_ratio)
            self._seen_ids.add(new_track.track_id)
            self._next_id += 1
            self._tracks.append(new_track)

        self._tracks = [track for track in self._tracks if track.misses <= self.max_track_age]
        return self._tracks, alerts

    def _predict_bbox(self, track: TrackState) -> tuple[int, int, int, int]:
        dx, dy = track.velocity
        x1, y1, x2, y2 = track.bbox
        return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

    @staticmethod
    def _estimate_velocity(
        previous_bbox: tuple[int, int, int, int],
        new_bbox: tuple[int, int, int, int],
    ) -> tuple[int, int]:
        previous_center = SimpleMultiObjectTracker._bbox_center(previous_bbox)
        new_center = SimpleMultiObjectTracker._bbox_center(new_bbox)
        return (new_center[0] - previous_center[0], new_center[1] - previous_center[1])

    @staticmethod
    def _bbox_center(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @staticmethod
    def _iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter_area
        return inter_area / union if union else 0.0

    @staticmethod
    def _determine_alert_state(track: TrackState, frame_shape: tuple[int, int, int], alert_area_ratio: float) -> str:
        height, width = frame_shape[:2]
        x1, y1, x2, y2 = track.bbox
        area_ratio = max(0, x2 - x1) * max(0, y2 - y1) / float(width * height)
        if area_ratio >= alert_area_ratio * 1.75:
            return "critical"
        if area_ratio >= alert_area_ratio or track.hits >= 6:
            return "watch"
        return "steady"

