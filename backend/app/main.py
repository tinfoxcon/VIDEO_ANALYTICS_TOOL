from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .schemas import AnalysisRequest, DemoSource, RunRecord, UploadedMedia
from .services.cvat_export import export_run_to_cvat
from .services.demo_sources import build_demo_source_list, prepare_demo_source
from .services.orchestrator import AnalysisOrchestrator
from .services.run_store import RunStore
from .services.uploads import store_uploaded_media


store = RunStore(settings.runs_dir)
orchestrator = AnalysisOrchestrator(settings=settings, store=store)

app = FastAPI(
    title="Smart Maritime Video Analytics PoC",
    version="0.1.0",
    summary="FastAPI backend for detection, tracking, visualization, and CVAT export.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://localhost:4173", "https://video-analytics-tool-9fyw.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=settings.data_dir), name="media")


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo/sources", response_model=list[DemoSource])
def list_demo_sources() -> list[DemoSource]:
    return build_demo_source_list(settings)


@app.post("/api/demo/sources/{source_id}/prepare", response_model=DemoSource)
def download_demo_source(source_id: str) -> DemoSource:
    try:
        return prepare_demo_source(settings, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/uploads/media", response_model=UploadedMedia)
def upload_media(file: UploadFile = File(...)) -> UploadedMedia:
    return store_uploaded_media(settings=settings, upload=file)


@app.get("/api/analysis/runs", response_model=list[RunRecord])
def list_runs() -> list[RunRecord]:
    return store.list()


@app.get("/api/analysis/runs/{run_id}", response_model=RunRecord)
def get_run(run_id: str) -> RunRecord:
    record = store.load(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return record


@app.post("/api/analysis/runs", response_model=RunRecord)
def create_run(request: AnalysisRequest) -> RunRecord:
    try:
        record = orchestrator.queue_run(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    orchestrator.start_run(record.run_id, request)
    return record


@app.post("/api/analysis/runs/{run_id}/export-cvat")
def export_cvat_bundle(run_id: str) -> dict[str, str]:
    record = store.load(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    if record.status != "completed":
        raise HTTPException(status_code=409, detail="Run must complete before CVAT export.")

    archive_path = export_run_to_cvat(run_record=record, workspace=settings.data_dir)
    return {"archive_path": str(archive_path), "message": "CVAT bundle created."}
