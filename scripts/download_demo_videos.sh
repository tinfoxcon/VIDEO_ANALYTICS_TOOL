#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INPUT_DIR="${ROOT_DIR}/backend/data/inputs"

mkdir -p "${INPUT_DIR}"

python3 "${ROOT_DIR}/scripts/build_mvtd_demo_video.py"
echo "Primary demo video is available in ${INPUT_DIR}"

