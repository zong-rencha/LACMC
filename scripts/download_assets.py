#!/usr/bin/env python3
"""Download and verify the versioned checkpoints, maps, and optional Docker image."""
import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
BASE = "https://github.com/zong-rencha/LACMC/releases/download/v1.3"
PARTS = [f"lacmc-qmix-1.3.tar.part-{i:03d}" for i in range(1, 5)]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name, expected=None):
    target = ARTIFACTS / name
    if expected and target.is_file() and sha256(target) == expected:
        print("Already verified:", name, flush=True)
        return target
    temporary = target.with_name(target.name + ".downloading")
    request = urllib.request.Request(f"{BASE}/{name}", headers={"User-Agent": "LACMC-reproduction"})
    print("Downloading:", name, flush=True)
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    if expected and sha256(temporary) != expected:
        raise RuntimeError(f"SHA256 mismatch: {name}. Download again before using this file.")
    temporary.replace(target)
    return target


def extract_checked(archive_path, destination, prefix):
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or ".." in relative.parts or not relative.parts
                    or relative.parts[0] != prefix or member.issym() or member.islnk()
                    or not (member.isfile() or member.isdir())):
                raise RuntimeError(f"Unexpected archive entry: {member.name}")
        # Validate existing files first, so an existing experiment is not overwritten.
        for member in members:
            if not member.isfile():
                continue
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if target.exists():
                digest = hashlib.sha256()
                stream = archive.extractfile(member)
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                if sha256(target) != digest.hexdigest():
                    raise RuntimeError(f"Existing file differs: {target}. Use a clean checkout.")
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="store_true", help="also download the prebuilt Docker image parts")
    args = parser.parse_args()
    ARTIFACTS.mkdir(exist_ok=True)
    checksum_file = download("SHA256SUMS")
    checksums = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        checksums[name.lstrip("*")] = digest
    download("release-manifest.json", checksums["release-manifest.json"])
    manifest = json.loads((ARTIFACTS / "release-manifest.json").read_text(encoding="utf-8"))
    image_parts = manifest.get("image_parts", PARTS)
    for name in image_parts:
        if Path(name).name != name or not name.endswith(tuple(f"{i:03d}" for i in range(1, 100))):
            raise RuntimeError(f"Invalid image part filename: {name}")
    names = ["models.tar.gz", "maps.tar.gz"] + (image_parts if args.image else [])
    for name in names:
        if name not in checksums:
            raise RuntimeError(f"Release checksum missing: {name}")
        download(name, checksums[name])
    extract_checked(ARTIFACTS / "models.tar.gz", ROOT, "results")
    extract_checked(ARTIFACTS / "maps.tar.gz", ROOT / "maps", "SMAC_Maps")
    manifest = json.loads((ARTIFACTS / "release-manifest.json").read_text(encoding="utf-8"))
    for model in manifest["models"]:
        if sha256(ROOT / model["path"]) != model["sha256"]:
            raise RuntimeError(f"Extracted model checksum mismatch: {model['path']}")
    (ROOT / "results" / "success_rate").mkdir(exist_ok=True)
    print("Checkpoints and maps ready. No evaluation directory or log is created.")


if __name__ == "__main__":
    main()
