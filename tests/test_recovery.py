import pytest

from cc_cep import recovery
from cc_cep.recovery import amended_jobs, check_runtime_unchanged
from cc_cep.study import progress


def test_progress_does_not_report_failed_jobs_as_completed():
    jobs = [
        {"attempts": [{"state": "COMPLETE"}]},
        {"attempts": [{"state": "FAILED"}]},
        {"attempts": []},
    ]
    assert progress(jobs) == {"completed_jobs": 1, "attempted_jobs": 2}


def test_recovery_cannot_retry_a_valid_unfavorable_result():
    with pytest.raises(ValueError, match="two failed"):
        amended_jobs(
            [{"id": "job", "attempts": [{"state": "FAILED"}, {"state": "COMPLETE"}]}], "job"
        )


def test_recovery_grants_only_one_extra_attempt():
    job = {"id": "job", "attempts": [{"state": "FAILED"}, {"state": "FAILED"}]}
    assert amended_jobs([job], "job")[0]["max_attempts"] == 3
    job["attempts"].append({"state": "FAILED"})
    with pytest.raises(ValueError, match="two failed"):
        amended_jobs([job], "job")


def test_recovery_refuses_changed_measurement_code(tmp_path, monkeypatch):
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    for root in (previous / "frozen", current):
        (root / "src/cc_cep").mkdir(parents=True)
        (root / "experiments").mkdir()
        (root / "deploy").mkdir()
        for name in (
            "src/cc_cep/core.py",
            "uv.lock",
            "experiments/load.js",
            "deploy/benchmark.yaml",
        ):
            (root / name).write_text("same")
    monkeypatch.setattr(recovery, "ROOT", current)
    check_runtime_unchanged(previous)
    (current / "src/cc_cep/core.py").write_text("changed")
    with pytest.raises(ValueError, match="measurement/runtime changed"):
        check_runtime_unchanged(previous)
