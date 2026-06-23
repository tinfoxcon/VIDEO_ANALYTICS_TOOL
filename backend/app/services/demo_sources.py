from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..schemas import DemoSource


def build_demo_source_list(settings: Settings) -> list[DemoSource]:
    sources: list[DemoSource] = []
    for source in settings.sample_sources:
        sources.append(
            DemoSource(
                id=source.id,
                title=source.title,
                description=source.description,
                source_page=source.source_page,
                download_url=source.download_url,
                local_path=str(source.local_path),
                exists_locally=source.local_path.exists(),
                license_name=source.license_name,
            )
        )
    return sources


def resolve_source_path(settings: Settings, source_id: str, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    for source in settings.sample_sources:
        if source.id == source_id:
            return source.local_path

    raise ValueError(f"Unknown source id: {source_id}")

