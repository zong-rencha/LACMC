#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
[[ -f SC2-Linux/StarCraftII/Versions/Base75689/SC2_x64 ]] || { echo 'Prepare Linux SC2 4.10 first.' >&2; exit 1; }
[[ -f results/agent/model-mac_0.pt ]] || { echo 'Download the release checkpoints first.' >&2; exit 1; }
mkdir -p results/success_rate
exec docker run --rm --gpus all \
    --cpus=4 --memory=8g --memory-swap=8g --shm-size=1g \
    -e OMP_NUM_THREADS=2 -e MKL_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=2 \
    --mount "type=bind,source=$PWD/SC2-Linux/StarCraftII,target=/opt/StarCraftII,readonly" \
    --mount "type=bind,source=$PWD/results,target=/app/src/results" \
    lacmc-qmix:1.3 python -u evaluate3.py
