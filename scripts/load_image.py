#!/usr/bin/env python3
"""Verify and stream the split release image to docker load without a second full copy."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from download_assets import ARTIFACTS, PARTS, sha256


def main():
    checksums = {}
    for line in (ARTIFACTS / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        checksums[name.lstrip("*")] = digest
    manifest = json.loads((ARTIFACTS / "release-manifest.json").read_text(encoding="utf-8"))
    parts = manifest.get("image_parts", PARTS)
    whole = hashlib.sha256()
    for name in parts:
        part = ARTIFACTS / name
        if sha256(part) != checksums[name]:
            raise RuntimeError(f"Image part checksum mismatch: {name}")
        with part.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                whole.update(block)
    if whole.hexdigest() != manifest["image_archive_sha256"]:
        raise RuntimeError("Combined Docker archive checksum mismatch")
    process = subprocess.Popen(["docker", "load"], stdin=subprocess.PIPE)
    try:
        for name in parts:
            with (ARTIFACTS / name).open("rb") as stream:
                shutil.copyfileobj(stream, process.stdin, length=1024 * 1024)
        process.stdin.close()
        code = process.wait()
    except BaseException:
        process.terminate()
        process.wait()
        raise
    if code:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
