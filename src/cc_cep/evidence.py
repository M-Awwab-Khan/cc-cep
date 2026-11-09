"""Portable, self-contained, checksum-verified trial evidence."""

import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


def snapshot_source(output):
    files = [ROOT / name for name in ("pyproject.toml", "uv.lock", "AGENTS.md")]
    files += [
        ROOT / name for name in ("README.md", "Makefile", ".gitignore") if (ROOT / name).is_file()
    ]
    files += [
        p
        for p in ROOT.iterdir()
        if p.is_file() and p.suffix in {".tex", ".bib", ".cls", ".sty", ".bst"}
    ]
    files += [p for p in (ROOT / "thumbnails").glob("*") if p.is_file()]
    for folder in ("src", "tests", "scripts", "deploy", "experiments", "docs", "analysis"):
        files += [
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix in {".py", ".mjs", ".json", ".yaml", ".js", ".toml", ".md", ".txt"}
        ]
    with tarfile.open(output / "source.tar.gz", "w:gz") as archive:
        for path in sorted(files):
            archive.add(path, arcname=str(path.relative_to(ROOT)))


def file_sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def seal(directory, exclude=None):
    exclude = set(exclude or ())
    if exclude - {"watchdog.log"}:
        raise ValueError("only the explicitly live watchdog log may remain unsealed")
    checks = {
        p.name: file_sha256(p)
        for p in directory.iterdir()
        if p.is_file() and p.name != "checksums.json" and p.name not in exclude
    }
    (directory / "checksums.json").write_text(json.dumps(checks, indent=2) + "\n")


def verify(directory):
    checks = json.loads((directory / "checksums.json").read_text())
    if not {"metadata.json", "events.jsonl", "summary.json"} <= checks.keys():
        raise ValueError("incomplete evidence manifest")
    for name, expected in checks.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise ValueError("unsafe evidence path")
        file = directory / name
        if file.is_symlink() or file_sha256(file) != expected:
            raise ValueError(f"evidence checksum mismatch: {file}")
    return json.loads((directory / "summary.json").read_text())
