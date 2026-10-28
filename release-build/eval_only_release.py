"""Build and promote a verified evaluation-only image; manual workflow only."""
import concurrent.futures
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT = pathlib.Path.cwd()
REPO = "zong-rencha/LACMC"
RELEASE_ID = 426209298
STAGING_TAG = "v1.3-eval-only-staging-20261028"
IMAGE = "lacmc-qmix:1.3"
PREVIOUS = "lacmc-qmix:previous-full"
EXPECTED = {"cmac-dtr-1.3.tar.part-001":{"sha256":"feb6fe1ce1d5710ace60637902a5e26a5b1122eed43fa4ba7186e7e47d66bcd2","bytes":1073741824},"cmac-dtr-1.3.tar.part-002":{"sha256":"a407ad538591bec749f4c8a39ff42fb26de262b72d167b1fc126112b08b3c6f4","bytes":1073741824},"cmac-dtr-1.3.tar.part-003":{"sha256":"db978a7f8110cfb4d2243d1a1b1ee518688382224ec1e9b5bdaf478f5f21e8d0","bytes":1073741824},"cmac-dtr-1.3.tar.part-004":{"sha256":"dadbf6267a07935272628fbe140013bbadbd0407a649b33687258e536bb2e4f3","bytes":170476093},"maps.tar.gz":{"sha256":"31e754dd553fb57a2b1da0705f4ae0ac2c050300bbdcd3aa148574d61a78c406","bytes":69385},"models.tar.gz":{"sha256":"0a5247044f185198e855e158cb92c93a5c6db825cb98962640c237aa1f37b123","bytes":99639648},"release-manifest.json":{"sha256":"7129b9d6c2131b91ecbbf17f0b8bde93f2c093381658fd90427a1bb5a3998ed1","bytes":20041},"SHA256SUMS":{"sha256":"3c1c02f506c9c07c8dd7f98749f02316cb508c02e595381df6ac70ba2a81ecf4","bytes":614}}
HELPERS = ROOT / "release-build"

def run(*args, capture=False):
    result = subprocess.run(list(args), check=True, capture_output=capture, text=capture)
    return result.stdout if capture else None

def api(path, method="GET", body=None):
    args = ["gh", "api", "--method", method, path]
    if body is None:
        text = run(*args, capture=True)
    else:
        result = subprocess.run(args + ["--input", "-"], input=json.dumps(body), text=True, check=True, capture_output=True)
        text = result.stdout
    return json.loads(text) if text.strip() else None

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def download(url, path, wanted):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and sha256(path) == wanted:
        return
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "LACMC-evaluation-only-release"})
            with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as output:
                shutil.copyfileobj(response, output, 4 * 1024 * 1024)
            assert sha256(path) == wanted, "Download digest mismatch: " + path.name
            return
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))

def check_existing_release():
    release = api(f"repos/{REPO}/releases/{RELEASE_ID}")
    assert release["tag_name"] == "v1.3"
    actual = {a["name"]: {"sha256": a["digest"].removeprefix("sha256:"), "bytes": a["size"]} for a in release["assets"]}
    assert actual == EXPECTED, "The current release changed; refuse to overwrite"
    return release

def verify_parts(directory, manifest):
    combined = hashlib.sha256()
    for name in manifest["image_parts"]:
        with (directory / name).open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                combined.update(chunk)
    assert combined.hexdigest() == manifest["image_archive_sha256"]

def load_parts(directory, manifest):
    loader = subprocess.Popen(["docker", "load"], stdin=subprocess.PIPE)
    decompressor = subprocess.Popen(["gzip", "-dc"], stdin=subprocess.PIPE, stdout=loader.stdin)
    loader.stdin.close()
    for name in manifest["image_parts"]:
        with (directory / name).open("rb") as stream:
            shutil.copyfileobj(stream, decompressor.stdin, 4 * 1024 * 1024)
    decompressor.stdin.close()
    assert decompressor.wait() == 0
    assert loader.wait() == 0

def audit_archive(archive, expected):
    allowed = {r["path"]: r["sha256"] for r in expected}
    seen = {}
    with tarfile.open(archive, "r:") as outer:
        saved = json.load(outer.extractfile("manifest.json"))
        assert len(saved) == 1 and IMAGE in saved[0]["RepoTags"]
        for layer in saved[0]["Layers"]:
            with outer.extractfile(layer) as layer_stream, tarfile.open(fileobj=layer_stream, mode="r|") as entries:
                for member in entries:
                    name = member.name.removeprefix("./").lstrip("/")
                    assert not name.startswith("opt/smac2/"), name
                    if not member.isfile() or not name.startswith("app/src/"):
                        continue
                    relative = name.removeprefix("app/src/")
                    assert relative in allowed, "Unexpected project file in a layer: " + name
                    content = entries.extractfile(member).read()
                    assert hashlib.sha256(content).hexdigest() == allowed[relative], name
                    assert b"def train(" not in content and b"def save_models(" not in content, name
                    seen[relative] = allowed[relative]
    assert seen == allowed, "Missing evaluation files"
    print("LAYER_AUDIT_OK: only 19 approved project files in all image layers", flush=True)

class PartWriter:
    def __init__(self, directory):
        self.directory = directory
        self.index = 0
        self.current = None
        self.used = 0
        self.digest = hashlib.sha256()
        self.paths = []
    def write(self, data):
        self.digest.update(data)
        offset = 0
        while offset < len(data):
            if self.current is None or self.used == 1024 ** 3:
                if self.current:
                    self.current.close()
                self.index += 1
                path = self.directory / f"lacmc-qmix-1.3-eval-only.tar.part-{self.index:03d}"
                self.paths.append(path)
                self.current = path.open("wb")
                self.used = 0
            chunk = data[offset:offset + min(len(data) - offset, 1024 ** 3 - self.used)]
            self.current.write(chunk)
            self.used += len(chunk)
            offset += len(chunk)
        return len(data)
    def flush(self):
        if self.current:
            self.current.flush()
    def close(self):
        if self.current:
            self.current.close()

def build():
    old_release = check_existing_release()
    free = shutil.disk_usage(ROOT).free
    if free < 40 * 1024 ** 3:
        run("sudo", "rm", "-rf", "/usr/local/lib/android", "/usr/share/dotnet", "/opt/ghc")
    assert shutil.disk_usage(ROOT).free > 30 * 1024 ** 3, "Insufficient temporary runner disk"
    original = ROOT / "original-assets"
    original.mkdir(exist_ok=True)
    def fetch(asset):
        name = asset["name"]
        download(asset["browser_download_url"], original / name, EXPECTED[name]["sha256"])
        print("Verified previous asset:", name, flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch, old_release["assets"]))
    manifest = json.loads((original / "release-manifest.json").read_text())
    verify_parts(original, manifest)
    load_parts(original, manifest)
    run("docker", "tag", IMAGE, PREVIOUS)
    previous_id = json.loads(run("docker", "image", "inspect", PREVIOUS, capture=True))[0]["Id"]
    previous_packages = sorted(run("docker", "run", "--rm", "--network", "none", "--entrypoint", "python", PREVIOUS, "-m", "pip", "freeze", capture=True).splitlines())
    for name in manifest["image_parts"]:
        (original / name).unlink()
    context = ROOT / "build-context"
    context.mkdir()
    shutil.copyfile(HELPERS / "Dockerfile.eval-only", context / "Dockerfile")
    (context / "licenses").mkdir()
    shutil.copyfile(ROOT / "licenses/DEPLOYMENT-MIT-LICENSE", context / "licenses/PROJECT-MIT-LICENSE")
    shutil.copyfile(ROOT / "licenses/SMAC-LICENSE", context / "licenses/SMAC-LICENSE")
    text = run("docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,source={ROOT},target=/work", "--entrypoint", "python",
               PREVIOUS, "/work/release-build/prepare_evaluation_image.py", "/app/src", "/work/build-context/runtime/src", capture=True)
    runtime = json.loads(text)
    expected_runtime = json.loads((HELPERS / "expected-runtime-files.json").read_text())
    assert runtime == expected_runtime, "Cloud source differs from the locally validated source"
    run("docker", "build", "--provenance=false", "--build-arg", "SOURCE_IMAGE=" + PREVIOUS, "-t", IMAGE, str(context))
    info = json.loads(run("docker", "image", "inspect", IMAGE, capture=True))[0]
    packages = sorted(run("docker", "run", "--rm", "--network", "none", "--entrypoint", "python", IMAGE, "-m", "pip", "freeze", capture=True).splitlines())
    assert packages == previous_packages, "Environment package versions changed"
    run("docker", "run", "--rm", "--network", "none", "--cpus=2", "--memory=2g", IMAGE, "python", "-c", "import evaluate3, torch, smac; print('CLOUD_EVALUATOR_IMPORT_OK')")
    run("docker", "image", "rm", PREVIOUS)
    run("docker", "builder", "prune", "-af")
    archive = ROOT / "evaluation-image.tar"
    run("docker", "save", "-o", str(archive), IMAGE)
    audit_archive(archive, runtime)
    output = ROOT / "new-assets"
    output.mkdir()
    writer = PartWriter(output)
    with archive.open("rb") as source, gzip.GzipFile(filename="", fileobj=writer, mode="wb", compresslevel=1, mtime=0) as compressed:
        shutil.copyfileobj(source, compressed, 4 * 1024 * 1024)
    writer.close()
    archive.unlink()
    required_models = {"results/agent/model-mac_0.pt"} | {f"results/adapter/adapter_{i}.pt" for i in range(1, 10)}
    original_models = {record["path"]: record for record in manifest["models"]}
    assert required_models <= set(original_models)
    copied = set()
    with tarfile.open(original / "models.tar.gz", "r:gz") as previous_models, tarfile.open(output / "models.tar.gz", "w:gz") as new_models:
        for member in previous_models:
            name = member.name.removeprefix("./")
            if name not in required_models:
                continue
            assert member.isfile()
            content = previous_models.extractfile(member).read()
            assert hashlib.sha256(content).hexdigest() == original_models[name]["sha256"]
            info_member = tarfile.TarInfo(name)
            info_member.size = len(content)
            info_member.mode = 0o644
            import io
            new_models.addfile(info_member, io.BytesIO(content))
            copied.add(name)
    assert copied == required_models
    manifest["previous_checkpoint_count"] = len(manifest["models"])
    manifest["models"] = [original_models[name] for name in sorted(required_models)]
    manifest["evaluation_checkpoint_count"] = len(required_models)
    manifest["previous_image_provenance"] = {k: manifest.get(k) for k in ["repository", "source_commit", "workflow_run", "local_image_id", "image_archive_sha256"]}
    manifest.update({
        "image": IMAGE, "local_image_id": info["Id"], "rootfs_diff_ids": info["RootFS"]["Layers"],
        "repository": "https://github.com/" + REPO, "source_commit": os.environ["GITHUB_SHA"],
        "workflow_run": f"https://github.com/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        "image_archive_sha256": writer.digest.hexdigest(), "image_archive_format": "gzip",
        "image_parts": [p.name for p in writer.paths],
        "build_origin": "evaluation-only multi-stage rebuild; original Python dependencies preserved",
        "evaluation_only": True, "runtime_files": runtime, "environment_packages": packages,
        "validation": {"local_forward_all_ten_tasks": "exact match, max_abs_error=0.0", "all_layers_project_file_audit": "passed"},
        "original_validated_image_id": "sha256:d15bf21c2465ffdebe3b5033767321e63fa049355b9c7348b2a664088283f4bf"
    })
    (output / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    sums = {"maps.tar.gz": EXPECTED["maps.tar.gz"]["sha256"], "models.tar.gz": sha256(output / "models.tar.gz")}
    sums.update({p.name: sha256(p) for p in writer.paths})
    sums["release-manifest.json"] = sha256(output / "release-manifest.json")
    (output / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name,digest in sums.items()))
    run("gh", "release", "create", STAGING_TAG, "--repo", REPO, "--draft", "--target", os.environ["GITHUB_SHA"],
        "--title", "Temporary evaluation-only image validation", "--notes", "Temporary candidate; do not publish. Promote only after full local evaluation passes.")
    for path in list(writer.paths) + [output / "models.tar.gz", output / "release-manifest.json", output / "SHA256SUMS"]:
        run("gh", "release", "upload", STAGING_TAG, str(path), "--repo", REPO)
    staging = api(f"repos/{REPO}/releases")
    stage = next(r for r in staging if r["tag_name"] == STAGING_TAG)
    expected_assets = {p.name: sha256(p) for p in output.iterdir() if p.is_file()}
    assert stage["draft"] and {a["name"]: a["digest"].removeprefix("sha256:") for a in stage["assets"]} == expected_assets
    print("EVALUATION_ONLY_CANDIDATE_READY " + str(stage["id"]), flush=True)

def publish():
    proof_path = HELPERS / "local-validation.json"
    proof = json.loads(proof_path.read_text())
    assert proof["forward_max_abs_error"] == 0.0
    assert proof["full_evaluation_exit_code"] == 0 and proof["maps"] == 10 and proof["episodes_per_map"] == 32
    assert proof["runtime_files"] == json.loads((HELPERS / "expected-runtime-files.json").read_text())
    release = check_existing_release()
    candidates = api(f"repos/{REPO}/releases")
    candidate = next(r for r in candidates if r["tag_name"] == STAGING_TAG)
    assert candidate["draft"]
    output = ROOT / "candidate-assets"
    output.mkdir()
    run("gh", "release", "download", STAGING_TAG, "--repo", REPO, "--dir", str(output))
    for asset in candidate["assets"]:
        assert sha256(output / asset["name"]) == asset["digest"].removeprefix("sha256:")
    manifest = json.loads((output / "release-manifest.json").read_text())
    assert manifest["evaluation_only"] and manifest["runtime_files"] == proof["runtime_files"]
    verify_parts(output, manifest)
    checksums = {}
    for line in (output / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        checksums[name.lstrip("*")] = digest
    assert set(checksums) == set(manifest["image_parts"] + ["models.tar.gz", "maps.tar.gz", "release-manifest.json"])
    for path in output.iterdir():
        if path.name != "SHA256SUMS":
            assert sha256(path) == checksums[path.name]
    assert checksums["maps.tar.gz"] == EXPECTED["maps.tar.gz"]["sha256"]
    assert len(manifest["models"]) == 10 and manifest["evaluation_checkpoint_count"] == 10
    notes = (HELPERS / "release-notes.md").read_text()
    api(f"repos/{REPO}/releases/{RELEASE_ID}", "PATCH", {"draft": True})
    for asset in release["assets"]:
        if asset["name"] != "maps.tar.gz":
            api(f"repos/{REPO}/releases/assets/{asset['id']}", "DELETE")
    for path in sorted(output.iterdir()):
        run("gh", "release", "upload", "v1.3", str(path), "--repo", REPO)
    final = api(f"repos/{REPO}/releases/{RELEASE_ID}")
    wanted = {p.name: sha256(p) for p in output.iterdir()}
    wanted["maps.tar.gz"] = EXPECTED["maps.tar.gz"]["sha256"]
    assert {a["name"]: a["digest"].removeprefix("sha256:") for a in final["assets"]} == wanted
    api(f"repos/{REPO}/releases/{RELEASE_ID}", "PATCH", {"draft": False, "name": "v1.3: LACMC evaluation-only Docker image", "body": notes})
    run("gh", "release", "delete", STAGING_TAG, "--repo", REPO, "--yes")
    print("V1_3_REPLACED_AND_PUBLISHED_WITH_VERIFIED_EVALUATION_ONLY_IMAGE", flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "build":
        build()
    elif sys.argv[1] == "publish":
        publish()
    else:
        raise ValueError("Unknown phase")
