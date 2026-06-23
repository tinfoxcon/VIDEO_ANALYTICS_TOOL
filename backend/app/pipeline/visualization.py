from __future__ import annotations

from typing import Any


def compose_visualization_frame(
    original_frame: Any,
    enhanced_frame: Any,
    tracks: list[Any],
    frame_index: int,
    elapsed_seconds: float,
    controls: Any,
    diagnostics: dict[str, float],
    cv2: Any,
) -> Any:
    left_panel = original_frame.copy()
    right_panel = enhanced_frame.copy()

    for track in tracks:
        x1, y1, x2, y2 = track.bbox
        color = _track_color(track.track_id, track.alert_state)
        cv2.rectangle(right_panel, (x1, y1), (x2, y2), color, 2)
        label_text = f"T{track.track_id} {track.label} {track.confidence:.2f}"
        cv2.putText(
            right_panel,
            label_text,
            (x1, max(24, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

        for index in range(1, len(track.history)):
            cv2.line(right_panel, track.history[index - 1], track.history[index], color, 2)

    stacked = cv2.hconcat([left_panel, right_panel]) if controls.comparison_view else right_panel
    canvas = cv2.copyMakeBorder(stacked, 72, 0, 0, 0, cv2.BORDER_CONSTANT, value=(7, 16, 22))

    header_lines = [
        f"Smart Maritime Analytics PoC | frame {frame_index} | t={elapsed_seconds:0.1f}s",
        (
            f"disturbance={controls.disturbance_profile} | threshold={controls.confidence_threshold:.2f} "
            f"| interval={controls.detection_interval} | active tracks={len(tracks)}"
        ),
        (
            f"glare_pixels={int(diagnostics.get('glare_pixels', 0))} "
            f"| sharpen={diagnostics.get('sharpen_strength', 0.0):.2f} "
            f"| temporal={diagnostics.get('temporal_smoothing', 0.0):.2f}"
        ),
    ]

    for index, line in enumerate(header_lines):
        cv2.putText(
            canvas,
            line,
            (18, 24 + index * 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (230, 244, 247),
            1,
            cv2.LINE_AA,
        )
    return canvas


def _track_color(track_id: int, alert_state: str) -> tuple[int, int, int]:
    if alert_state == "critical":
        return (0, 78, 255)
    if alert_state == "watch":
        return (0, 200, 255)

    palette = [
        (110, 240, 172),
        (255, 162, 75),
        (120, 196, 255),
        (187, 140, 255),
        (255, 225, 110),
    ]
    return palette[(track_id - 1) % len(palette)]

