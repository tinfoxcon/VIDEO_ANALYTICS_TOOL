from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from ..pipeline.runtime import load_runtime_modules
from ..schemas import RunRecord


def export_run_to_cvat(run_record: RunRecord, workspace: Path) -> Path:
    modules = load_runtime_modules()
    cv2 = modules["cv2"]

    if run_record.artifacts is None:
        raise ValueError("Run does not contain artifacts yet.")

    input_video_path = workspace / run_record.artifacts.input_video.removeprefix("/media/")
    timeline_path = workspace / run_record.artifacts.timeline_json.removeprefix("/media/")
    if not input_video_path.exists() or not timeline_path.exists():
        raise FileNotFoundError("Run artifacts are missing on disk; export cannot continue.")

    export_root = workspace / "cvat" / run_record.run_id
    images_dir = export_root / "images"
    export_root.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    with timeline_path.open("r", encoding="utf-8") as file_handle:
        timeline = json.load(file_handle)

    capture = cv2.VideoCapture(str(input_video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open input video for CVAT export: {input_video_path}")

    image_id = 1
    frame_to_file: dict[int, str] = {}
    try:
        timeline_frames = {entry["frame_index"] for entry in timeline}
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index in timeline_frames:
                filename = f"{image_id:06d}.jpg"
                cv2.imwrite(str(images_dir / filename), frame)
                frame_to_file[frame_index] = filename
                image_id += 1
            frame_index += 1
    finally:
        capture.release()

    coco = {
        "images": [],
        "annotations": [],
        "categories": [{"id": 1, "name": "boat"}, {"id": 2, "name": "candidate-boat"}],
    }
    annotation_id = 1
    image_lookup = {filename: index for index, filename in enumerate(frame_to_file.values(), start=1)}
    for frame_index, filename in frame_to_file.items():
        coco["images"].append({"id": image_lookup[filename], "file_name": filename, "width": 0, "height": 0})
        timeline_entry = next(item for item in timeline if item["frame_index"] == frame_index)
        for track in timeline_entry["tracks"]:
            x1, y1, x2, y2 = track["bbox"]
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            coco["annotations"].append(
                {
                    "id": annotation_id,
                    "image_id": image_lookup[filename],
                    "category_id": 1 if track["label"] == "boat" else 2,
                    "bbox": [x1, y1, width, height],
                    "area": width * height,
                    "iscrowd": 0,
                    "attributes": {
                        "track_id": track["track_id"],
                        "confidence": track["confidence"],
                        "alert_state": track["alert_state"],
                    },
                }
            )
            annotation_id += 1

    with (export_root / "annotations.coco.json").open("w", encoding="utf-8") as file_handle:
        json.dump(coco, file_handle, indent=2)

    with (export_root / "README.txt").open("w", encoding="utf-8") as file_handle:
        file_handle.write(
            "Import the image directory and COCO annotations into CVAT.\n"
            "The export contains frames sampled from the analysis timeline together with predicted boxes.\n"
        )

    archive_path = workspace / "cvat" / f"{run_record.run_id}-cvat-export.zip"
    with ZipFile(archive_path, "w") as archive:
        for path in export_root.rglob("*"):
            archive.write(path, path.relative_to(export_root.parent))
    return archive_path

