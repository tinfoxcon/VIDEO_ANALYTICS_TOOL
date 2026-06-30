from __future__ import annotations

import importlib
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

from ..config import SampleSource, Settings
from ..schemas import DemoSource

MVTD_DATASET_BASE = (
    "https://huggingface.co/datasets/AhsanBB/Maritime_Visual_Tracking_Dataset_MVTD/"
    "resolve/main/test/23-Boat"
)
MVTD_FRAME_COUNT = 120
MVTD_FRAME_RATE = 12.0


def build_demo_source_list(settings: Settings) -> list[DemoSource]:
    return [_serialize_demo_source(source) for source in settings.sample_sources]


def prepare_demo_source(settings: Settings, source_id: str) -> DemoSource:
    source = _find_demo_source(settings, source_id)
    source.local_path.parent.mkdir(parents=True, exist_ok=True)
    if not source.local_path.exists():
        try:
            if source.id == "mvtd-23-boat":
                _build_mvtd_demo_video(settings, source.local_path)
            else:
                _download_direct_video(source.download_url, source.local_path, referer=source.source_page)
        except (OSError, RuntimeError):
            _build_synthetic_demo_video(source.local_path, source.title)
    return _serialize_demo_source(source)


def resolve_source_path(settings: Settings, source_id: str, explicit_path: str | None) -> Path:
    if explicit_path:
        return _resolve_uploaded_media_path(settings, explicit_path)

    return _find_demo_source(settings, source_id).local_path


def _resolve_uploaded_media_path(settings: Settings, explicit_path: str) -> Path:
    raw_value = explicit_path.strip()
    if not raw_value:
        raise ValueError("Uploaded media reference is empty. Please upload the file again.")

    candidates: list[Path] = []
    upload_dir = settings.upload_dir.resolve()
    data_dir = settings.data_dir.resolve()

    if raw_value.startswith("/media/"):
        media_relative = Path(raw_value.removeprefix("/media/"))
        candidate = _resolve_within(data_dir, media_relative)
        if candidate is not None:
            candidates.append(candidate)

    raw_path = Path(raw_value).expanduser()
    if raw_path.is_absolute():
        candidates.append(raw_path.resolve(strict=False))
        candidates.append(upload_dir / raw_path.name)
    elif len(raw_path.parts) == 1:
        candidates.append(upload_dir / raw_path.name)
    elif raw_path.parts[0] == "uploads":
        candidate = _resolve_within(data_dir, raw_path)
        if candidate is not None:
            candidates.append(candidate)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    raise FileNotFoundError("Uploaded media is no longer available on the backend. Please upload it again.")


def _resolve_within(base_dir: Path, relative_path: Path) -> Path | None:
    candidate = (base_dir / relative_path).resolve(strict=False)
    try:
        candidate.relative_to(base_dir)
    except ValueError:
        return None
    return candidate


def _serialize_demo_source(source: SampleSource) -> DemoSource:
    return DemoSource(
        id=source.id,
        title=source.title,
        description=source.description,
        source_page=source.source_page,
        download_url=source.download_url,
        local_path=str(source.local_path),
        exists_locally=source.local_path.exists(),
        license_name=source.license_name,
    )


def _find_demo_source(settings: Settings, source_id: str) -> SampleSource:
    for source in settings.sample_sources:
        if source.id == source_id:
            return source
    raise ValueError(f"Unknown source id: {source_id}")


def _download_direct_video(url: str, destination: Path, referer: str | None = None) -> None:
    temp_path = destination.with_suffix(f"{destination.suffix}.tmp")
    headers = {"Referer": referer} if referer else None
    _download_file(url, temp_path, use_existing=False, extra_headers=headers)
    temp_path.replace(destination)


def _build_mvtd_demo_video(settings: Settings, output_video: Path) -> None:
    frame_dir = settings.input_dir / "mvtd-23-boat-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    downloaded_frames: list[Path] = []
    for frame_index in range(1, MVTD_FRAME_COUNT + 1):
        frame_name = f"{frame_index:08d}.jpg"
        frame_path = frame_dir / frame_name
        frame_url = f"{MVTD_DATASET_BASE}/{frame_name}?download=true"
        _download_file(frame_url, frame_path, use_existing=True, extra_headers=None)
        downloaded_frames.append(frame_path)

    try:
        cv2 = importlib.import_module("cv2")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "OpenCV is not installed on the backend. Install opencv-python-headless to prepare demo videos."
        ) from exc

    first_frame = cv2.imread(str(downloaded_frames[0]))
    if first_frame is None:
        raise RuntimeError("Unable to load the first MVTD frame for video assembly.")

    height, width = first_frame.shape[:2]
    temp_output = output_video.with_suffix(".tmp.mp4")
    writer = cv2.VideoWriter(
        str(temp_output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        MVTD_FRAME_RATE,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Unable to open video writer for {output_video}")

    try:
        for frame_path in downloaded_frames:
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise RuntimeError(f"Unable to read downloaded frame: {frame_path.name}")
            writer.write(frame)
    finally:
        writer.release()

    temp_output.replace(output_video)


def _build_synthetic_demo_video(output_video: Path, title: str) -> None:
    modules = _load_cv_modules()
    cv2 = modules["cv2"]
    np = modules["numpy"]

    width = 1280
    height = 720
    frame_rate = 12.0
    frame_count = 180
    temp_output = output_video.with_suffix(".tmp.mp4")
    writer = cv2.VideoWriter(
        str(temp_output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        frame_rate,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Unable to open video writer for {output_video}")

    try:
        for frame_index in range(frame_count):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            _paint_synthetic_scene(frame, frame_index, cv2, np)
            cv2.putText(
                frame,
                f"{title} demo",
                (28, 44),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (244, 246, 248),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                "Synthetic fallback clip prepared locally",
                (28, 82),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (218, 229, 235),
                2,
                cv2.LINE_AA,
            )
            writer.write(frame)
    finally:
        writer.release()

    temp_output.replace(output_video)


def _paint_synthetic_scene(frame: object, frame_index: int, cv2: object, np: object) -> None:
    height, width = frame.shape[:2]
    horizon = int(height * 0.42)
    frame[:horizon] = (186, 160, 112)
    frame[horizon:] = (132, 88, 34)

    for stripe_index in range(9):
        y = horizon + 14 + stripe_index * 28
        offset = int(((frame_index * 6) + stripe_index * 37) % 90)
        cv2.line(frame, (offset - 80, y), (width, y + 12), (156, 109, 48), 2, cv2.LINE_AA)

    primary_x = (frame_index * 8) % (width + 220) - 220
    secondary_x = width - ((frame_index * 5) % (width + 180))
    tertiary_x = (frame_index * 3) % (width + 140) - 140
    _draw_boat(frame, primary_x, int(height * 0.60), 1.05, cv2, np)
    _draw_boat(frame, secondary_x, int(height * 0.70), 0.82, cv2, np)
    _draw_boat(frame, tertiary_x, int(height * 0.78), 0.62, cv2, np)


def _draw_boat(frame: object, x: int, y: int, scale: float, cv2: object, np: object) -> None:
    hull_width = max(72, int(118 * scale))
    hull_height = max(18, int(28 * scale))
    cabin_width = max(24, int(42 * scale))
    cabin_height = max(18, int(24 * scale))

    hull = [
        (x, y),
        (x + hull_width, y),
        (x + hull_width - int(18 * scale), y + hull_height),
        (x + int(14 * scale), y + hull_height),
    ]
    cv2.fillPoly(frame, [np.array(hull, dtype="int32")], (236, 236, 238))
    cv2.rectangle(
        frame,
        (x + int(22 * scale), y - cabin_height),
        (x + int(22 * scale) + cabin_width, y),
        (247, 247, 249),
        -1,
    )
    cv2.line(
        frame,
        (x + int(12 * scale), y + hull_height + 6),
        (x - int(22 * scale), y + hull_height + 6),
        (216, 224, 230),
        max(2, int(3 * scale)),
        cv2.LINE_AA,
    )


def _load_cv_modules() -> dict[str, object]:
    try:
        return {
            "cv2": importlib.import_module("cv2"),
            "numpy": importlib.import_module("numpy"),
        }
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "OpenCV and NumPy are required to prepare demo videos on the backend."
        ) from exc


def _download_file(
    url: str,
    destination: Path,
    use_existing: bool,
    extra_headers: dict[str, str] | None,
) -> None:
    if use_existing and destination.exists():
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0", **(extra_headers or {})}
    request = Request(url, headers=headers)
    with urlopen(request, timeout=60) as response, destination.open("wb") as output_handle:
        shutil.copyfileobj(response, output_handle)
