# Brief Documentation

## 1. Purpose

This Proof of Concept (PoC) demonstrates a computer-vision-enabled smart video analytics workflow for early detection of maritime targets in recorded video. The implementation combines a React operator interface, a FastAPI backend, OpenCV-based image enhancement and motion analysis, PyTorch-based object detection, Docker packaging, and CVAT export support for annotation review.

## 2. Algorithms Implemented

### 2.1 Digitisation and Video Ingestion

- Input video is accepted as a local MP4 file or selected from a configured demo source.
- The acquisition step copies the selected input into the run output folder as a digitised reference video so that the original input used for analysis is preserved for review and traceability.

### 2.2 Image Enhancement and Noise Handling

The preprocessing stage is designed to improve visibility of maritime targets under difficult scene conditions such as blur, haze, glare, and surface reflections.

Implemented methods:

- Contrast enhancement using CLAHE in LAB color space.
- Glare and reflection suppression using HSV brightness masking and local smoothing.
- Sharpening using unsharp masking.
- Optional temporal smoothing using weighted blending with the previous frame.
- Disturbance simulation for PoC demonstration:
  - blur
  - haze/cloud-like washout
  - reflective sea-surface highlights
  - mixed disturbance mode

These controls are operator-adjustable from the UI to show how environmental noise can be reduced interactively.

### 2.3 Target Detection

The PoC uses a hybrid detection approach:

1. PyTorch / TorchVision detector
   - A pretrained `Faster R-CNN MobileNetV3 FPN` detector is used.
   - The detector focuses on the COCO `boat` class.
   - Detection runs at a configurable interval instead of every frame to reduce compute load.

2. OpenCV motion-cue detector
   - Background subtraction (`MOG2`) is used to detect moving objects.
   - Binary thresholding and morphological cleanup reduce speckle noise.
   - Contour filtering removes very small or unrealistic candidate boxes.

3. Hybrid fusion
   - Model detections and motion detections are merged using overlap checks.
   - Motion cues help maintain candidate targets between deep-learning inference frames.
   - This improves responsiveness for small or partially visible maritime targets.

### 2.4 Tracking

Tracking is implemented using a lightweight multi-object tracker based on bounding-box overlap and simple motion prediction.

Implemented tracking logic:

- Each confirmed detection is assigned a persistent track ID.
- Track association uses Intersection over Union (IoU).
- A simple velocity estimate predicts the next box position.
- Tracks remain alive for a configurable number of missed frames.
- Each track stores:
  - ID
  - class label
  - confidence
  - bounding box
  - age
  - miss count
  - short trajectory history

### 2.5 Alerting and Visualisation

- Alert state is estimated from target persistence and apparent target size in the scene.
- Alert levels include `steady`, `watch`, and `critical`.
- Annotated output includes:
  - bounding boxes
  - track IDs
  - confidence labels
  - track trails
  - frame/time metadata
  - operator control settings
- A split-screen view compares disturbed/raw imagery against enhanced and tracked output.

## 3. System Workflow

### 3.1 Digitisation Workflow

1. The operator selects a recorded maritime clip from the UI or local source list.
2. The backend creates a run folder for the analysis session.
3. The input video is copied into the run folder as the digitised input artifact.
4. This preserved copy becomes the reference for subsequent detection, tracking, and export steps.

### 3.2 Detection Workflow

1. Video frames are read sequentially using OpenCV.
2. A selected disturbance profile may be applied for PoC stress testing.
3. Enhancement is applied to improve contrast and suppress reflections/noise.
4. The PyTorch detector runs periodically to detect `boat` objects.
5. The OpenCV motion detector runs to identify moving target candidates.
6. Model detections and motion proposals are fused into a unified detection set.

### 3.3 Tracking Workflow

1. Fused detections are matched against existing tracks using IoU.
2. Matching tracks are updated with new position, confidence, and trajectory history.
3. Unmatched detections create new tracks.
4. Unmatched old tracks are retained temporarily until their miss threshold is exceeded.
5. Alert state is recalculated based on target persistence and relative size.
6. The system writes:
   - annotated output video
   - preview image
   - timeline JSON
   - run metadata

### 3.4 Review and Annotation Workflow

1. The operator reviews the processed result from the React UI.
2. Track summaries and alerts are displayed for quick assessment.
3. A sampled-frame export can be generated for CVAT.
4. CVAT can then be used to review or correct predictions and create improved annotations for future training or evaluation.

## 4. Assumptions

- The PoC is intended for recorded video, not a fully integrated live sensor feed.
- Generic pretrained object-detection weights are used; no maritime-specific fine-tuning has been applied.
- The main detection class is `boat`; detailed vessel-type identification is outside current scope.
- The tracker is designed for explainability and fast iteration, not for high-density maritime traffic scenes.
- The operator UI is a conceptual prototype and does not represent a complete operational command-and-control system.

## 5. Limitations

- Performance depends strongly on video quality, target scale, sea state, and camera stability.
- Small, heavily occluded, distant, or low-contrast targets may be missed.
- False positives may occur from waves, wakes, glare, shoreline clutter, or moving reflections.
- The current tracker uses simple box association and does not include re-identification or advanced motion modelling.
- Disturbance handling is heuristic and intended for demonstration, not mission-grade environmental compensation.
- CVAT is integrated through export workflow only; embedded CVAT session management is not implemented inside the UI.
- CUDA acceleration is supported by design, but actual runtime performance depends on the deployment environment and available GPU support.

## 6. Summary

The PoC demonstrates an end-to-end maritime video analytics concept consisting of digitisation, enhancement, hybrid detection, multi-object tracking, operator review, alerting, and CVAT-assisted annotation refinement. The system is intentionally lightweight and modular so that maritime-specific models, stronger tracking methods, and live-stream integration can be added in future development stages.
