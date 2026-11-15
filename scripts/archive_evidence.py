"""Archive non-secret implementation/configuration and ALL local trial evidence."""

import argparse
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Relative subtree to omit (for example an actively changing study)",
    )
    args = parser.parse_args()
    if not args.name or Path(args.name).name != args.name:
        raise ValueError("archive name must be a filename stem")
    destination = ROOT / "results/archives" / f"{args.name}.tar.gz"
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = [
        ROOT / name for name in ("pyproject.toml", "uv.lock", "README.md", "AGENTS.md", "Makefile")
    ]
    files += [
        p
        for p in ROOT.iterdir()
        if p.is_file() and p.suffix in {".tex", ".bib", ".cls", ".sty", ".bst"}
    ]
    files += [
        p
        for p in (ROOT / "thumbnails").glob("*")
        if p.is_file() and p.suffix in {".jpeg", ".jpg", ".png", ".svg"}
    ]
    for folder in (
        "src",
        "tests",
        "scripts",
        "deploy",
        "experiments",
        "analysis",
        "docs",
        "results/raw",
        "results/curated",
    ):
        files.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and "__pycache__" not in p.parts
            and "frozen" not in p.relative_to(ROOT).parts
            and p.suffix != ".pyc"
        )
    excluded = [(ROOT / name).resolve() for name in args.exclude]
    if any(not path.is_relative_to(ROOT) for path in excluded):
        raise ValueError("excluded paths must be within the project")
    files = sorted(p for p in set(files) if not any(p.is_relative_to(x) for x in excluded))
    # Paths are allowlisted above: no .tools, .venv, .git, kubeconfig, or credentials.
    with tarfile.open(destination, "w:gz") as archive:
        for path in files:
            archive.add(path, arcname=str(path.relative_to(ROOT)))
    record = {
        "archive": str(destination.relative_to(ROOT)),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": len(files),
        "bytes": destination.stat().st_size,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "contains": "Current source/configuration and all local development trial evidence",
        "excluded_subtrees": args.exclude,
        "limitation": "Not every superseded intermediate source version was snapshotted; see results/README.md",
    }
    (ROOT / "results/curated" / f"{args.name}-manifest.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
