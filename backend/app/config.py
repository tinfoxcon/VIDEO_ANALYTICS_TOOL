from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(slots=True)
class SampleSource:
    id: str
    title: str
    description: str
    local_path: Path
    download_url: str
    source_page: str
    license_name: str


@dataclass(slots=True)
class Settings:
    repo_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    frontend_origin: str = field(default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"))
    default_device: str = field(default_factory=lambda: os.getenv("TORCH_DEVICE", "auto"))

    @property
    def backend_dir(self) -> Path:
        return self.repo_root / "backend"

    @property
    def data_dir(self) -> Path:
        return self.backend_dir / "data"

    @property
    def input_dir(self) -> Path:
        return self.data_dir / "inputs"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def cvat_dir(self) -> Path:
        return self.data_dir / "cvat"

    @property
    def runs_dir(self) -> Path:
        return self.output_dir / "runs"

    @property
    def sample_sources(self) -> list[SampleSource]:
        return [
            SampleSource(
                id="mvtd-23-boat",
                title="MVTD Test Sequence 23-Boat",
                description=(
                    "Maritime Visual Tracking Dataset sequence assembled into an MP4 from the "
                    "public Hugging Face dataset frames."
                ),
                local_path=self.input_dir / "mvtd-23-boat.mp4",
                download_url=(
                    "https://huggingface.co/datasets/AhsanBB/"
                    "Maritime_Visual_Tracking_Dataset_MVTD/tree/main/test/23-Boat"
                ),
                source_page=(
                    "https://huggingface.co/datasets/AhsanBB/"
                    "Maritime_Visual_Tracking_Dataset_MVTD/tree/main/test/23-Boat"
                ),
                license_name="CC0-1.0",
            ),
            SampleSource(
                id="pexels-coastal-traffic",
                title="Pexels Coastal Boat Traffic",
                description=(
                    "Full-HD coastal boat traffic footage used as the primary maritime "
                    "PoC sequence for detection and tracking."
                ),
                local_path=self.input_dir / "pexels-coastal-traffic.mp4",
                download_url=(
                    "https://videos.pexels.com/video-files/17842168/"
                    "17842168-hd_1920_1080_30fps.mp4"
                ),
                source_page="https://www.pexels.com/search/videos/boat%20sea/",
                license_name="Pexels License",
            ),
            SampleSource(
                id="pexels-channel-transit",
                title="Pexels Channel Transit",
                description=(
                    "Supplementary maritime clip for alternate camera angle and vessel movement."
                ),
                local_path=self.input_dir / "pexels-channel-transit.mp4",
                download_url=(
                    "https://videos.pexels.com/video-files/32078691/"
                    "13679072_1080_1920_25fps.mp4"
                ),
                source_page="https://www.pexels.com/search/videos/boat%20sea/",
                license_name="Pexels License",
            ),
        ]


settings = Settings()
