# CVAT Workflow

The backend includes an `export-cvat` API step that creates a ZIP bundle with:

- sampled JPEG frames
- `annotations.coco.json`
- a short import note

Use that ZIP as the bridge into CVAT for annotation refinement or validation.

## Recommended CVAT startup

Follow the official CVAT installation guide and README:

- https://docs.cvat.ai/docs/administration/basics/installation/
- https://github.com/cvat-ai/cvat

Typical local startup flow:

```bash
git clone https://github.com/cvat-ai/cvat
cd cvat
docker compose up -d
docker exec -it cvat_server bash -ic 'python3 ~/manage.py createsuperuser'
```

## Using the PoC export

1. Run an analysis job from the React operator UI or through `POST /api/analysis/runs`.
2. Trigger `POST /api/analysis/runs/{run_id}/export-cvat`.
3. Upload the generated ZIP contents into a CVAT task as images plus COCO annotations.
4. Review or correct bounding boxes, then export labels back out for future fine-tuning or evaluation.

