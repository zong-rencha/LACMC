$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$sc2 = Join-Path $project 'SC2-Linux\StarCraftII'
$results = Join-Path $project 'results'
if (-not (Test-Path -LiteralPath "$sc2\Versions\Base75689\SC2_x64")) { throw 'Prepare Linux SC2 4.10 first.' }
if (-not (Test-Path -LiteralPath "$results\agent\model-mac_0.pt")) { throw 'Download the release checkpoints first.' }
New-Item -ItemType Directory -Path "$results\success_rate" -Force | Out-Null
docker run --rm --gpus all `
    --cpus=4 --memory=8g --memory-swap=8g --shm-size=1g `
    -e OMP_NUM_THREADS=2 -e MKL_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=2 `
    --mount "type=bind,source=$sc2,target=/opt/StarCraftII,readonly" `
    --mount "type=bind,source=$results,target=/app/src/results" `
    lacmc-qmix:1.3 python -u evaluate3.py
exit $LASTEXITCODE
