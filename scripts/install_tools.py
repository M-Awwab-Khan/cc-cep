#!/usr/bin/env python3
"""Install project-local Linux x86_64 tools with publisher checksum verification.

No sudo, no global PATH edits, no cluster operations. Re-run uses exact pinned releases.
"""

import hashlib
import io
import json
import platform
import re
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".tools" / "bin"
VERSIONS = {
    "kind": "v0.33.0",
    "istioctl": "1.31.3",
    "k6": "v2.3.0",
    "helm": "v4.3.1",
    "kubectl": "v1.36.0",
}


def get(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def install(name, url, checksum_url, member=None):
    data = get(url)
    checksums = get(checksum_url).decode()
    filename = url.rsplit("/", 1)[1]
    lines = [line for line in checksums.splitlines() if filename in line]
    line = lines[0] if lines else checksums.strip()
    match = re.search(r"\b[a-fA-F0-9]{64}\b", line)
    actual = hashlib.sha256(data).hexdigest()
    if not match or actual != match.group().lower():
        raise RuntimeError(f"publisher checksum mismatch for {name}")
    binary = data
    if member:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            candidate = archive.getmember(member)
            if not candidate.isfile():
                raise RuntimeError("archive member is not a file")
            binary = archive.extractfile(candidate).read()
    target = DEST / name
    target.write_bytes(binary)
    target.chmod(0o755)
    print(f"Installed {name} {VERSIONS[name]}", flush=True)
    return {
        "version": VERSIONS[name],
        "url": url,
        "archive_sha256": actual,
        "binary_sha256": hashlib.sha256(binary).hexdigest(),
    }


def main():
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise SystemExit("This installer currently supports Linux x86_64 only")
    DEST.mkdir(parents=True, exist_ok=True)
    assets = [
        (
            "kind",
            "https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64",
            ".sha256sum",
            None,
        ),
        (
            "istioctl",
            "https://github.com/istio/istio/releases/download/1.31.3/istioctl-1.31.3-linux-amd64.tar.gz",
            ".sha256",
            "istioctl",
        ),
        ("kubectl", "https://dl.k8s.io/release/v1.36.0/bin/linux/amd64/kubectl", ".sha256", None),
        (
            "helm",
            "https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz",
            ".sha256sum",
            "linux-amd64/helm",
        ),
        (
            "k6",
            "https://github.com/grafana/k6/releases/download/v2.3.0/k6-v2.3.0-linux-amd64.tar.gz",
            "https://github.com/grafana/k6/releases/download/v2.3.0/k6-v2.3.0-checksums.txt",
            "k6-v2.3.0-linux-amd64/k6",
        ),
    ]
    records = {}
    for name, url, checksum, member in assets:
        records[name] = install(
            name, url, checksum if checksum.startswith("https:") else url + checksum, member
        )
        (ROOT / "deploy" / "tools.lock.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()
