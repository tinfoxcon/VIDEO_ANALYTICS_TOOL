#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
from urllib.request import Request, urlopen

import cv2


DATASET_BASE = (
    "https://huggingface.co/datasets/AhsanBB/Maritime_Visual_Tracking_Dataset_MVTD/"
    "resolve/main/test/23-Boat"
)
FRAME_COUNT = 120
FRAME_RATE = 12.0


def download_file(url: str, destination: Path) -> None:
    if destination.exists():
        return

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response, destination.open("wb") as output_handle:
        shutil.copyfileobj(response, output_handle)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_dir = repo_root / "backend" / "data" / "inputs"
    frame_dir = input_dir / "mvtd-23-boat-frames"
    output_video = input_dir / "mvtd-23-boat.mp4"
    input_dir.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    downloaded_frames: list[Path] = []
    for frame_index in range(1, FRAME_COUNT + 1):
        frame_name = f"{frame_index:08d}.jpg"
        frame_path = frame_dir / frame_name
        frame_url = f"{DATASET_BASE}/{frame_name}?download=true"
        download_file(frame_url, frame_path)
        downloaded_frames.append(frame_path)

    first_frame = cv2.imread(str(downloaded_frames[0]))
    if first_frame is None:
        raise RuntimeError("Unable to load the first MVTD frame for video assembly.")

    height, width = first_frame.shape[:2]
    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FRAME_RATE,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Unable to open video writer for {output_video}")

    try:
        for frame_path in downloaded_frames:
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise RuntimeError(f"Unable to read downloaded frame: {frame_path}")
            writer.write(frame)
    finally:
        writer.release()

    print(f"Created {output_video}")


if __name__ == "__main__":
    main()
