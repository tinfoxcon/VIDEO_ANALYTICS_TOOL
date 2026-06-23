from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .runtime import load_runtime_modules


COCO_LABELS = [
    "__background__",
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
]


@dataclass(slots=True)
class Detection:
    bbox: tuple[int, int, int, int]
    score: float
    label: str
    source: str


class MotionCueDetector:
    def __init__(self) -> None:
        self._modules = load_runtime_modules()
        self.cv2 = self._modules["cv2"]
        self.background_subtractor = self.cv2.createBackgroundSubtractorMOG2(
            history=120,
            varThreshold=20,
            detectShadows=False,
        )

    def detect(self, frame: Any, min_box_area: int) -> list[Detection]:
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        mask = self.background_subtractor.apply(gray)
        _, mask = self.cv2.threshold(mask, 220, 255, self.cv2.THRESH_BINARY)
        kernel = self.cv2.getStructuringElement(self.cv2.MORPH_ELLIPSE, (5, 5))
        mask = self.cv2.morphologyEx(mask, self.cv2.MORPH_OPEN, kernel)
        mask = self.cv2.morphologyEx(mask, self.cv2.MORPH_DILATE, kernel, iterations=2)
        contours, _ = self.cv2.findContours(mask, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)

        proposals: list[Detection] = []
        for contour in contours:
            x, y, w, h = self.cv2.boundingRect(contour)
            area = w * h
            if area < min_box_area:
                continue
            aspect_ratio = w / max(h, 1)
            if aspect_ratio < 0.6 or aspect_ratio > 6.5:
                continue
            proposals.append(
                Detection(
                    bbox=(x, y, x + w, y + h),
                    score=0.35,
                    label="maritime-motion",
                    source="motion",
                )
            )
        return proposals


class TorchVisionMaritimeDetector:
    def __init__(self, device_preference: str = "auto") -> None:
        self._modules = load_runtime_modules()
        self.cv2 = self._modules["cv2"]
        self.np = self._modules["numpy"]
        self.torch = self._modules["torch"]
        self.torchvision = self._modules["torchvision"]
        self.device = self._resolve_device(device_preference)
        self.model = None
        self.weights = None

    def _resolve_device(self, device_preference: str) -> str:
        if device_preference == "cpu":
            return "cpu"
        if self.torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _ensure_model(self) -> None:
        if self.model is not None:
            return

        detection_module = self.torchvision.models.detection
        self.weights = detection_module.FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT
        self.model = detection_module.fasterrcnn_mobilenet_v3_large_320_fpn(weights=self.weights)
        self.model.eval()
        self.model.to(self.device)

    def detect(self, frame: Any, confidence_threshold: float, min_box_area: int) -> list[Detection]:
        self._ensure_model()

        rgb_frame = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        tensor = self.torch.from_numpy(rgb_frame).permute(2, 0, 1).float() / 255.0
        with self.torch.no_grad():
            prediction = self.model([tensor.to(self.device)])[0]

        detections: list[Detection] = []
        for box, score, label_index in zip(
            prediction["boxes"].detach().cpu().numpy(),
            prediction["scores"].detach().cpu().numpy(),
            prediction["labels"].detach().cpu().numpy(),
        ):
            if int(label_index) >= len(COCO_LABELS):
                continue
            label_name = COCO_LABELS[int(label_index)]
            if label_name != "boat" or float(score) < confidence_threshold:
                continue

            x1, y1, x2, y2 = [int(value) for value in box]
            area = max(0, x2 - x1) * max(0, y2 - y1)
            if area < min_box_area:
                continue

            detections.append(
                Detection(
                    bbox=(x1, y1, x2, y2),
                    score=float(score),
                    label="boat",
                    source="model",
                )
            )
        return detections


class HybridMaritimeDetector:
    def __init__(self, device_preference: str = "auto") -> None:
        self.model_detector = TorchVisionMaritimeDetector(device_preference=device_preference)
        self.motion_detector = MotionCueDetector()

    @property
    def device(self) -> str:
        return self.model_detector.device

    def detect(self, frame: Any, controls: Any, frame_index: int) -> list[Detection]:
        model_detections = []
        if frame_index % controls.detection_interval == 0:
            model_detections = self.model_detector.detect(
                frame=frame,
                confidence_threshold=controls.confidence_threshold,
                min_box_area=controls.min_box_area,
            )

        motion_detections = self.motion_detector.detect(frame=frame, min_box_area=controls.min_box_area)
        return self._fuse(model_detections, motion_detections, controls.motion_weight)

    def _fuse(
        self,
        model_detections: list[Detection],
        motion_detections: list[Detection],
        motion_weight: float,
    ) -> list[Detection]:
        if not model_detections:
            return motion_detections

        fused = list(model_detections)
        for motion_detection in motion_detections:
            overlaps = [
                self._intersection_over_union(model_detection.bbox, motion_detection.bbox)
                for model_detection in model_detections
            ]
            if overlaps and max(overlaps) > 0.2:
                continue
            boosted_score = min(0.8, motion_detection.score * max(motion_weight, 0.1))
            fused.append(
                Detection(
                    bbox=motion_detection.bbox,
                    score=boosted_score,
                    label="candidate-boat",
                    source=motion_detection.source,
                )
            )
        return fused

    @staticmethod
    def _intersection_over_union(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        denom = area_a + area_b - inter_area
        return inter_area / denom if denom else 0.0

