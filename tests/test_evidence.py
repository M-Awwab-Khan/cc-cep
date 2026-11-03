import json
from dataclasses import replace

import pytest

from cc_cep.analysis import analyze
from cc_cep.core import Config
from cc_cep.simulation import simulate


def test_seeded_evidence_and_tamper_detection(tmp_path):
    cfg = replace(Config(), duration=3, expected_treatment_requests=60000, max_rps=25000)
    # Reserve must still fit the small availability allocation.
    cfg = replace(cfg, reserve_seconds=0.0001)
    a = simulate(cfg, 5, "abort", tmp_path / "a")
    b = simulate(cfg, 5, "abort", tmp_path / "b")
    assert a["ledgers"] == b["ledgers"]
    assert a["cleanup_verified"]
    assert analyze(tmp_path)["runs"] == 2
    (tmp_path / "a" / "events.jsonl").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        analyze(tmp_path)


def test_contamination_is_invalid_not_causal_evidence(tmp_path):
    summary = simulate(Config(), 1, "abort", tmp_path / "run", contaminated=True)
    assert "isolation" in summary["stop_reason"]
    assert summary["cleanup_verified"]
    assert json.loads((tmp_path / "run" / "metadata.json").read_text())["mode"] == "simulation"
