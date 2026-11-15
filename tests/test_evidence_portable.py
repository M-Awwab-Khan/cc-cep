import json
import tarfile

import pytest

from cc_cep import evidence


def test_mutable_guardian_log_does_not_invalidate_failed_run_evidence(tmp_path):
    for name in ("metadata.json", "events.jsonl", "summary.json"):
        (tmp_path / name).write_text("{}")
    (tmp_path / "watchdog.log").write_text("still running")
    (tmp_path / "watchdog-at-failure.log").write_text("immutable snapshot")
    evidence.seal(tmp_path, exclude={"watchdog.log"})
    (tmp_path / "watchdog.log").write_text("later independent cleanup")
    evidence.verify(tmp_path)
    assert "watchdog-at-failure.log" in json.loads((tmp_path / "checksums.json").read_text())
    with pytest.raises(ValueError, match="only"):
        evidence.seal(tmp_path, exclude={"summary.json"})


def test_source_bundle_excludes_runtime_credentials_and_tools(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    for name in ["pyproject.toml", "uv.lock", "AGENTS.md"]:
        (root / name).write_text("public")
    (root / "kubeconfig.local").write_text("secret")
    (root / ".env").write_text("secret")
    (root / "src").mkdir()
    (root / "src/example.py").write_text("public")
    output = tmp_path / "bundle"
    output.mkdir()
    monkeypatch.setattr(evidence, "ROOT", root)
    evidence.snapshot_source(output)
    with tarfile.open(output / "source.tar.gz") as archive:
        names = archive.getnames()
    assert "src/example.py" in names
    assert "kubeconfig.local" not in names and ".env" not in names
