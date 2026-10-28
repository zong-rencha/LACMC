#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "${1:-}" != --accept-license ]]; then
    echo 'Read Blizzard AI and Machine Learning License before installing:'
    echo 'https://blzdistsc2-a.akamaihd.net/AI_AND_MACHINE_LEARNING_LICENSE.html'
    echo 'If you agree, run: bash scripts/setup_sc2.sh --accept-license'
    exit 1
fi
command -v curl >/dev/null || { echo 'Install curl first.' >&2; exit 1; }
command -v unzip >/dev/null || { echo 'Install unzip first.' >&2; exit 1; }
[[ -d maps/SMAC_Maps ]] || { echo 'Run python3 scripts/download_assets.py first.' >&2; exit 1; }
mkdir -p artifacts SC2-Linux
if [[ ! -f SC2-Linux/StarCraftII/Versions/Base75689/SC2_x64 ]]; then
    curl --fail --location --retry 5 --continue-at - \
        --output artifacts/SC2.4.10.zip \
        https://blzdistsc2-a.akamaihd.net/Linux/SC2.4.10.zip
    unzip -n -P iagreetotheeula artifacts/SC2.4.10.zip -d SC2-Linux
fi
chmod +x SC2-Linux/StarCraftII/Versions/Base75689/SC2_x64
mkdir -p SC2-Linux/StarCraftII/Maps/SMAC_Maps
cp -a maps/SMAC_Maps/. SC2-Linux/StarCraftII/Maps/SMAC_Maps/
echo 'SC2 4.10 and the experiment maps are ready.'
