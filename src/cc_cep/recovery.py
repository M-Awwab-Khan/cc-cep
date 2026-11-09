"""Explicit recovery amendment: preserve evidence, never retry a valid unfavorable result."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from .evidence import ROOT, verify
from .replay import replay
from .study import atomic_json, now, prepare


def check_runtime_unchanged(previous):
    frozen = previous / "frozen"
    paths = [
        p.relative_to(frozen)
        for p in (frozen / "src").rglob("*.py")
        if p.name not in {"study.py", "study_report.py"}
    ]
    paths += [Path(p) for p in ("uv.lock", "experiments/load.js", "deploy/benchmark.yaml")]
    for path in paths:
        if (frozen / path).read_bytes() != (ROOT / path).read_bytes():
            raise ValueError(f"measurement/runtime changed: {path}; requires a new study")


def validate_qualification(folder, config, no_fault):
    result = verify(folder)
    if result["state"] != "COMPLETE" or not result["cleanup_verified"]:
        raise ValueError("qualification must be complete with verified cleanup")
    metadata = json.loads((folder / "metadata.json").read_text())["config"]
    for key in (
        "rps_per_cohort",
        "warmup_seconds",
        "recovery_seconds",
        "interval_seconds",
        "family",
        "controller",
    ):
        if metadata[key] != config[key]:
            raise ValueError(f"qualification configuration differs: {key}")
    if metadata.get("no_fault", False) != no_fault or metadata["workload_seed"] < 9000:
        raise ValueError("qualification needs the declared fault mode and independent seed")
    replay(folder)


def amended_jobs(jobs, job_id):
    """Pure validation: exactly one additional attempt, solely for invalid execution."""
    matching = [j for j in jobs if j["id"] == job_id]
    if len(matching) != 1:
        raise ValueError("one matching failed job required")
    job = matching[0]
    if len(job["attempts"]) != 2 or any(a["state"] != "FAILED" for a in job["attempts"]):
        raise ValueError("only a job with two failed invalid attempts can be amended")
    job["max_attempts"] = 3
    return jobs


def recover(previous, directory, job_id, healthy, faulted):
    old = json.loads((previous / "matrix.json").read_text())
    if json.loads((previous / "status.json").read_text())["state"] != "STOPPED":
        raise ValueError("previous driver must be stopped")
    check_runtime_unchanged(previous)
    jobs = amended_jobs(old["jobs"], job_id)
    job = next(j for j in jobs if j["id"] == job_id)
    for attempt in job["attempts"]:
        summary = verify(previous / attempt["directory"])
        if not summary["cleanup_verified"] or not any(
            message in summary["stop_reason"]
            for message in (
                "load generator dropped eligible iterations",
                "load generator exited unsuccessfully",
            )
        ):
            raise ValueError("unsupported failure or unverified cleanup; cannot amend")
    validate_qualification(healthy, job["config"], True)
    validate_qualification(faulted, job["config"], False)
    prepare(
        directory,
        previous / "input-evidence/calibration/selected-loads.json",
        previous / "input-evidence/pilot-abort",
        previous / "input-evidence/pilot-delay",
    )
    current = json.loads((directory / "plan.json").read_text())
    if [(j["id"], j["config"]) for j in current["jobs"]] != [(j["id"], j["config"]) for j in jobs]:
        raise ValueError("protocol/order changed; cannot continue prior observations")
    for old_job in jobs:
        if Path(old_job["id"]).name != old_job["id"]:
            raise ValueError("unsafe job path")
        folder = previous / old_job["id"]
        if folder.exists():
            shutil.copytree(folder, directory / old_job["id"])
        for attempt in old_job["attempts"]:
            if attempt["state"] == "COMPLETE":
                replay(directory / attempt["directory"])
    evidence = directory / "recovery-evidence"
    evidence.mkdir()
    for name in (
        "plan.json",
        "matrix.json",
        "status.json",
        "source.tar.gz",
        "driver.log",
        "execution-notes.json",
    ):
        if (previous / name).exists():
            shutil.copy2(previous / name, evidence / ("previous-" + name))
    for folder in previous.glob("safety-*"):
        if folder.is_dir():
            shutil.copytree(folder, evidence / folder.name)
    for name, folder in (
        ("no-fault-qualification", healthy.parent),
        ("fault-qualification", faulted.parent),
    ):
        shutil.copytree(folder, evidence / name)
    amendment = {
        "created_utc": now(),
        "previous_study": str(previous),
        "job": job_id,
        "previous_matrix_sha256": hashlib.sha256(
            (previous / "matrix.json").read_bytes()
        ).hexdigest(),
        "additional_attempts_allowed": 1,
        "reason": "Two invalid load executions; independent full-length no-fault and fault-on diagnostics now pass. Underlying transient cause remains unresolved.",
        "limitations": "This is a post-failure retry-rule amendment, not the original predeclared protocol. All prior observations and failures remain; no valid result is retried.",
        "unchanged": "Controller, workload, deployment, phase lengths, order, budgets and planned analysis",
        "changes": "Administrative retry limit, read-only resource logging and corrected progress counts",
    }
    current.update(jobs=jobs, recovery_amendment=amendment, resource_context=True)
    atomic_json(directory / "recovery-amendment.json", amendment)
    atomic_json(directory / "plan.json", current)
    atomic_json(directory / "matrix.json", current)
    return directory / "frozen"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--job", required=True)
    parser.add_argument("--healthy", required=True, type=Path)
    parser.add_argument("--faulted", required=True, type=Path)
    args = parser.parse_args()
    print(
        recover(
            args.previous.resolve(),
            args.directory.resolve(),
            args.job,
            args.healthy.resolve(),
            args.faulted.resolve(),
        )
    )


if __name__ == "__main__":
    main()
