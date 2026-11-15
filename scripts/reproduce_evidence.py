"""Verify/extract single archives or a multi-part study index using only the stdlib.

Use --analyze after `uv sync --frozen`; when present, analysis imports the archived source.
"""

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path, PurePosixPath


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_filename(value):
    name = PurePosixPath(value)
    if name.is_absolute() or len(name.parts) != 1 or ".." in name.parts:
        raise ValueError("unsafe archive filename")
    return str(name)


def indexed_archive(record, base, destination):
    name = safe_filename(record["file"])
    if "parts" not in record:
        file = base / name
    else:
        if not record["parts"]:
            raise ValueError("empty archive parts")
        assembly = destination / ".assembled"
        assembly.mkdir(exist_ok=True)
        file = assembly / name
        seen = set()
        with file.open("xb") as output:
            for part in record["parts"]:
                part_name = safe_filename(part["file"])
                if part_name in seen:
                    raise ValueError("duplicate archive part")
                seen.add(part_name)
                path = base / part_name
                if path.is_symlink():
                    raise ValueError("archive part must not be a symlink")
                checksum = hashlib.sha256()
                with path.open("rb") as stream:
                    while block := stream.read(1024 * 1024):
                        checksum.update(block)
                        output.write(block)
                if checksum.hexdigest() != part["sha256"]:
                    raise ValueError(f"archive part checksum mismatch: {path}")
    if digest(file) != record["sha256"]:
        raise ValueError(f"archive checksum mismatch: {file}")
    return file


def main():
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--archive", type=Path)
    choice.add_argument("--index", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    source = args.archive or args.index
    expected = Path(str(source) + ".sha256").read_text().split()[0]
    if digest(source) != expected:
        raise ValueError("archive/index checksum mismatch")
    args.destination.mkdir(parents=True, exist_ok=False)
    if args.index:
        records = json.loads(source.read_text())["archives"]
        archives = []
        for record in records:
            archives.append(indexed_archive(record, source.parent, args.destination))
    else:
        archives = [source]
    for file in archives:
        with tarfile.open(file, "r:gz") as archive:
            archive.extractall(args.destination, filter="data")
    checked = 0
    for manifest in args.destination.rglob("checksums.json"):
        for name, expected in json.loads(manifest.read_text()).items():
            rel = PurePosixPath(name)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError("unsafe manifest path")
            target = manifest.parent / name
            if target.is_symlink() or digest(target) != expected:
                raise ValueError(f"evidence checksum mismatch: {target}")
        checked += 1
    print(f"Archives verified; {checked} evidence manifests verified")
    if args.analyze:
        archived = args.destination / "study/source.tar.gz"
        if archived.exists():
            code = args.destination / "archived-source"
            code.mkdir()
            with tarfile.open(archived, "r:gz") as archive:
                archive.extractall(code, filter="data")
            sys.path.insert(0, str(code / "src"))
        elif (args.destination / "src").is_dir():
            sys.path.insert(0, str(args.destination / "src"))
        from cc_cep.replay import replay
        from cc_cep.statistics import analyze_matrix

        for baseline in args.destination.rglob("baseline.json"):
            parent = baseline.parent
            summary = parent / "summary.json"
            if summary.exists() and json.loads(summary.read_text())["state"] == "COMPLETE":
                metadata = json.loads((parent / "metadata.json").read_text())
                if metadata.get("accounting_version") == "realized-cumulative-v2":
                    print(json.dumps(replay(parent)))
        for matrix in args.destination.rglob("matrix.json"):
            print(json.dumps(analyze_matrix(matrix.parent)))


if __name__ == "__main__":
    main()
