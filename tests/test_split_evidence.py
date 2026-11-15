import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


@pytest.mark.parametrize("failure", [None, "corrupt", "traversal"])
def test_split_archive_cli_reassembles_and_checks_each_part(tmp_path, failure):
    payload = b"verified experimental evidence"
    archive = tmp_path / "original.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        files = {
            "payload.txt": payload,
            "checksums.json": json.dumps(
                {"payload.txt": hashlib.sha256(payload).hexdigest()}
            ).encode(),
        }
        for name, value in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(value)
            output.addfile(info, io.BytesIO(value))
    data = archive.read_bytes()
    parts = []
    for number, block in enumerate((data[:37], data[37:])):
        name = f"evidence.part-{number}"
        (tmp_path / name).write_bytes(block)
        parts.append({"file": name, "sha256": hashlib.sha256(block).hexdigest()})
    if failure == "corrupt":
        (tmp_path / parts[1]["file"]).write_bytes(b"changed")
    if failure == "traversal":
        parts[0]["file"] = "../outside"
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "archives": [
                    {
                        "file": "evidence.tar.gz",
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "parts": parts,
                    }
                ]
            }
        )
    )
    Path(str(index) + ".sha256").write_text(hashlib.sha256(index.read_bytes()).hexdigest())
    destination = tmp_path / "extracted"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "scripts/reproduce_evidence.py"),
            "--index",
            str(index),
            "--destination",
            str(destination),
        ],
        capture_output=True,
        text=True,
    )
    if failure:
        assert result.returncode != 0
        assert not (destination / "payload.txt").exists()
        assert (
            "checksum mismatch" if failure == "corrupt" else "unsafe archive filename"
        ) in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert (destination / "payload.txt").read_bytes() == payload
        assert "1 evidence manifests verified" in result.stdout
