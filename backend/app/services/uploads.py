from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from ..config import Settings
from ..pipeline.runtime import load_runtime_modules
from ..schemas import UploadedMedia


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
VIDEO_SUFFIXES = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}


def store_uploaded_media(settings: Settings, upload: UploadFile) -> UploadedMedia:
    filename = (upload.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename.")

    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
        allowed = ", ".join(sorted(IMAGE_SUFFIXES | VIDEO_SUFFIXES))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported media type. Upload one of: {allowed}",
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = _slugify(Path(filename).stem) or "uploaded-media"
    unique_prefix = uuid4().hex[:10]
    original_path = settings.upload_dir / f"{unique_prefix}-{safe_stem}{suffix}"

    try:
        with original_path.open("wb") as file_handle:
            shutil.copyfileobj(upload.file, file_handle)
    finally:
        upload.file.close()

    if suffix in VIDEO_SUFFIXES:
        return UploadedMedia(
            title=_titleize(Path(filename).stem),
            original_filename=filename,
            source_path=str(original_path),
            media_kind="video",
        )

    normalized_video_path = settings.upload_dir / f"{unique_prefix}-{safe_stem}.mp4"
    _convert_image_to_video(original_path, normalized_video_path)
    return UploadedMedia(
        title=_titleize(Path(filename).stem),
        original_filename=filename,
        source_path=str(normalized_video_path),
        media_kind="image",
        converted_to_video=True,
        note=(
            "Still images are converted into a short MP4 clip. Detection will work, "
            "but tracking is limited because there is only one visual frame."
        ),
    )


def _convert_image_to_video(image_path: Path, video_path: Path) -> None:
    modules = load_runtime_modules()
    cv2 = modules["cv2"]
    image = cv2.imread(str(image_path))
    if image is None:
        raise HTTPException(status_code=400, detail=f"Unable to decode uploaded image: {image_path.name}")

    height, width = image.shape[:2]
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        6.0,
        (width, height),
    )
    try:
        for _ in range(18):
            writer.write(image)
    finally:
        writer.release()


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return normalized[:48]


def _titleize(value: str) -> str:
    cleaned = re.sub(r"[_-]+", " ", value).strip()
    return cleaned or "Uploaded Media"
