from __future__ import annotations

from typing import Any


def simulate_disturbance(frame: Any, profile: str, cv2: Any, np: Any) -> Any:
    """Inject synthetic maritime disturbances for PoC robustness demos."""
    if profile == "clear":
        return frame

    disturbed = frame.copy()
    height, width = disturbed.shape[:2]

    if profile in {"blurred", "mixed"}:
        disturbed = cv2.GaussianBlur(disturbed, (9, 9), 0)

    if profile in {"hazy", "mixed"}:
        haze_layer = np.full_like(disturbed, 255)
        disturbed = cv2.addWeighted(disturbed, 0.72, haze_layer, 0.28, 0)

    if profile in {"reflective", "mixed"}:
        overlay = disturbed.copy()
        for idx in range(5):
            center = (int(width * (0.15 + 0.16 * idx)), int(height * (0.55 + 0.05 * (idx % 2))))
            axes = (int(width * 0.08), int(height * 0.03))
            cv2.ellipse(overlay, center, axes, 0, 0, 360, (255, 255, 255), -1)
        disturbed = cv2.addWeighted(disturbed, 0.85, overlay, 0.15, 0)

    return disturbed


def enhance_frame(
    frame: Any,
    controls: Any,
    cv2: Any,
    np: Any,
    previous_frame: Any | None = None,
) -> tuple[Any, dict[str, float]]:
    """Apply lightweight enhancement stages that help recover boats in adverse scenes."""
    enhanced = frame.copy()

    if controls.enable_clahe:
        lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        enhanced = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)

    if controls.enable_glare_mask and controls.glare_suppression > 0:
        hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
        h_channel, s_channel, v_channel = cv2.split(hsv)
        glare_mask = cv2.inRange(v_channel, 215, 255)
        softened = cv2.GaussianBlur(v_channel, (19, 19), 0)
        corrected_v = np.where(glare_mask > 0, softened, v_channel).astype(v_channel.dtype)
        enhanced = cv2.cvtColor(cv2.merge((h_channel, s_channel, corrected_v)), cv2.COLOR_HSV2BGR)
    else:
        glare_mask = np.zeros(frame.shape[:2], dtype="uint8")

    if controls.sharpen_strength > 0:
        blur = cv2.GaussianBlur(enhanced, (0, 0), 3)
        enhanced = cv2.addWeighted(
            enhanced,
            1.0 + controls.sharpen_strength,
            blur,
            -controls.sharpen_strength,
            0,
        )

    if controls.enable_temporal_smoothing and previous_frame is not None and controls.temporal_smoothing > 0:
        enhanced = cv2.addWeighted(
            enhanced,
            1.0 - controls.temporal_smoothing,
            previous_frame,
            controls.temporal_smoothing,
            0,
        )

    diagnostics = {
        "glare_pixels": float(glare_mask.sum() / 255.0),
        "sharpen_strength": float(controls.sharpen_strength),
        "temporal_smoothing": float(controls.temporal_smoothing if previous_frame is not None else 0.0),
    }
    return enhanced, diagnostics

