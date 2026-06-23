# Smart Maritime Video Analytics PoC

Proof-of-concept implementation for early detection of maritime targets using:

- React operator UI
- FastAPI backend
- OpenCV preprocessing, visualization, and motion cues
- PyTorch object detection with optional CUDA
- Docker packaging
- CVAT export workflow for annotation review

## What the PoC demonstrates

### 1. Detection, identification, and tracking on recorded videos

- Recorded maritime video analysis on sample footage downloaded from the web
- Preliminary target detection and multi-target tracking with persistent IDs
- Operator-tunable robustness controls for blur, haze, and surface reflections
- Annotated output video with overlays, track trails, metadata, and alert states

### 2. Operator interface prototype

- Near-real-time job submission and run-status polling
- Threshold and noise-filter controls
- Track summaries and alert cards
- CVAT export action for annotation refinement

### 3. Deliverables mapped to the requirement

- Digitized input video copy: `backend/data/outputs/runs/<run_id>/digitized-input.mp4`
- Demonstration output video: `backend/data/outputs/runs/<run_id>/annotated-output.mp4`
- Working UI prototype: `frontend/`
- Brief documentation: this README plus files in `docs/`

## Repo layout

```text
backend/
  app/
  data/
frontend/
docs/
scripts/
docker-compose.yml
docker-compose.cuda.yml
```

## Sample videos sourced from the web

The primary demo source is `mvtd-23-boat`, assembled locally from the public MVTD maritime dataset frames hosted on Hugging Face:

- https://huggingface.co/datasets/AhsanBB/Maritime_Visual_Tracking_Dataset_MVTD/tree/main/test/23-Boat

Build the local MP4 with:

```bash
./scripts/download_demo_videos.sh
```

The repo also keeps two optional Pexels source definitions for UI/demo completeness, but the MVTD-derived clip is the recommended default because it is reproducible in restricted environments.

## Local run

### Option A: Docker

CPU:

```bash
docker compose up --build
```

CUDA:

```bash
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up --build
```

### Option B: Local processes

Backend:

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Render deployment

This repository keeps the FastAPI service in `backend/`, so a Render deploy from the repo root needs either:

- the included root `requirements.txt`, which forwards to `backend/requirements.txt`, or
- the included `render.yaml`, which sets the service `rootDir` to `backend`

If you create a Render web service manually from the repo root, use:

```bash
Build Command: pip install -r requirements.txt
Start Command: uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

If you deploy with Render Blueprint sync, `render.yaml` already uses the correct backend directory and start command.

## API endpoints

- `GET /api/health`
- `GET /api/demo/sources`
- `GET /api/analysis/runs`
- `GET /api/analysis/runs/{run_id}`
- `POST /api/analysis/runs`
- `POST /api/analysis/runs/{run_id}/export-cvat`

## Detection pipeline summary

1. Input footage is digitized and optionally disturbed for demo stress conditions.
2. OpenCV enhancement stages recover contrast and suppress glare.
3. PyTorch `torchvision` detection runs on the `boat` class.
4. OpenCV background motion cues add candidate targets between model inference frames.
5. An IoU tracker maintains track IDs and alert states.
6. The backend renders a comparison video and timeline artifacts consumed by the React UI.

See [docs/system-workflow.md](/Users/satya/Documents/SMART_VIDEO_ANALYTICS/docs/system-workflow.md) for the workflow diagram and [docs/cvat-workflow.md](/Users/satya/Documents/SMART_VIDEO_ANALYTICS/docs/cvat-workflow.md) for the annotation loop.

## Limitations

- The PoC uses generic pretrained weights rather than a maritime-specific model.
- Identification is class-level (`boat` / candidate boat), not vessel-type recognition.
- No camera stabilization, radar fusion, or georegistration is included.
- CVAT is integrated through export artifacts rather than an embedded live CVAT instance.
