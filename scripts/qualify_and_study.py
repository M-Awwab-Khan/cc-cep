"""Bounded sustained qualification, then a fresh study; never tunes against policy outcomes."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback

from cc_cep.cluster_smoke import smoke
from cc_cep.core import wilson
from cc_cep.evidence import ROOT, file_sha256, snapshot_source
from cc_cep.istio import IstioFault
from cc_cep.live import run
from cc_cep.qualification import SCREEN_CEILINGS, SCREEN_Z, qualifies
from cc_cep.replay import replay
from cc_cep.study import (
    atomic_json,
    capture_context,
    config_for,
    environment,
    now,
    prepare,
    runtime_fingerprint,
)


def cpu(cohort):
    command = [
        str(ROOT / ".tools/bin/kubectl"),
        "--kubeconfig",
        str(ROOT / "kubeconfig.local"),
        "--context",
        "kind-cc-cep",
        "-n",
        "cc-cep",
        "exec",
        "deployment/frontend-" + cohort,
        "-c",
        "app",
        "--",
        "cat",
        "/sys/fs/cgroup/cpu.stat",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
    return {key: int(value) for key, value in (line.split() for line in result.stdout.splitlines())}


def desktop_notice(message, directory):
    """Best-effort local notice to the user, only for exit/failure."""
    try:
        result = subprocess.run(
            ["notify-send", "CC-CEP research", message], capture_output=True, text=True, timeout=3
        )
        atomic_json(
            directory / "notification-status.json",
            {"utc": now(), "submitted": result.returncode == 0, "error": result.stderr[-1000:]},
        )
    except Exception as exc:
        atomic_json(
            directory / "notification-status.json",
            {"utc": now(), "submitted": False, "error": repr(exc)},
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-name", default="sustained-qualification-03")
    parser.add_argument("--study-name", default="full-study-v7")
    parser.add_argument("--seed-start", type=int, default=9301)
    args = parser.parse_args()
    if args.seed_start < 9000:
        raise ValueError("Qualification seeds must be separate from evaluation")
    for name in (args.qualification_name, args.study_name):
        if not name or "/" in name or ".." in name:
            raise ValueError("Names must be new filename stems")
    directory = ROOT / "results/raw" / args.qualification_name
    study = ROOT / "results/raw" / args.study_name
    directory.mkdir(exist_ok=False)
    if study.exists():
        raise FileExistsError(study)
    declaration = {
        "created_utc": now(),
        "rates_in_order": [32, 64, 32, 64],
        "seeds": list(range(args.seed_start, args.seed_start + 4)),
        "phases_seconds": [120, 300, 120],
        "no_fault": True,
        "qualification": "All four must complete, replay, retain >=400 seconds of post-baseline traffic per cohort, have per-stream 99% Wilson upper screening bounds <=0.5% availability-bad and <=2.5% latency-bad outcomes (50% SLO headroom; no joint coverage claim), unchanged pods, <=0.70 average frontend CPU cores and <=5% wall-time CPU throttling. Any failure halts; no automatic rate search or retry.",
        "next_study": "Fresh 110-trial replacement at 32/64 requests/s; no earlier comparisons pooled. Full phases and controller unchanged. Costs retain independent 48 requests/s pilots.",
    }
    atomic_json(directory / "qualification-plan.json", declaration)
    snapshot_source(directory)
    measurement_paths = [
        *sorted((ROOT / "src").rglob("*.py")),
        ROOT / "scripts/qualify_and_study.py",
        ROOT / "experiments/load.js",
        ROOT / "deploy/benchmark.yaml",
        ROOT / "uv.lock",
    ]
    measurement_hashes = {str(p.relative_to(ROOT)): file_sha256(p) for p in measurement_paths}
    atomic_json(directory / "measurement-source.json", measurement_hashes)
    state = {
        "state": "QUALIFYING",
        "pid": os.getpid(),
        "completed_qualifications": 0,
        "planned_qualifications": 4,
        "main_study_running": False,
        "directory": str(directory),
        "heartbeat_path": str(directory / "heartbeat.json"),
    }
    status = ROOT / "results/curated/active-study.json"
    atomic_json(status, state | {"updated_utc": now()})
    stop = threading.Event()

    def context():
        while not stop.wait(30):
            atomic_json(
                directory / "heartbeat.json",
                {
                    "utc": now(),
                    "pid": os.getpid(),
                    "active_rate": state.get("active_rate"),
                    "completed_qualifications": state["completed_qualifications"],
                },
            )
            try:
                capture_context(directory)
            except Exception as exc:
                with (directory / "context-errors.log").open("a") as log:
                    log.write(repr(exc) + "\n")

    child = None

    def terminate(*_):
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, terminate)
    worker = threading.Thread(target=context, daemon=True)
    worker.start()
    records = []
    try:
        restored = json.loads(
            (ROOT / "results/raw/stall-stack-diagnosis-01/restoration.json").read_text()
        )
        if not restored or not all(value is True for value in restored.values()):
            raise RuntimeError("temporary instrumentation has not been restored")
        qualified_environment = environment()
        qualified_runtime = runtime_fingerprint(IstioFault())
        atomic_json(
            directory / "qualification-environment.json",
            {"packages": qualified_environment, "runtime": qualified_runtime},
        )
        costs = json.loads((ROOT / "results/raw/full-study-v3/plan.json").read_text())["costs"]
        for index, rate in enumerate(declaration["rates_in_order"]):
            if (
                environment() != qualified_environment
                or runtime_fingerprint(IstioFault()) != qualified_runtime
            ):
                raise RuntimeError("runtime or package environment changed during qualification")
            state.update(active_rate=rate, active_repetition=index + 1)
            atomic_json(status, state | {"updated_utc": now()})
            config = config_for(
                rate, "delay", "threshold", declaration["seeds"][index], costs, kind="control"
            )
            path = directory / f"qualification-{index + 1}-{rate}"
            config_path = directory / (path.name + ".json")
            atomic_json(config_path, config)
            safety = directory / ("safety-" + str(index + 1))
            smoke(safety)
            before = {c: cpu(c) for c in ("control", "treatment")}
            started = time.monotonic()
            result = run(config_path, safety / "integration.json", path)
            elapsed = time.monotonic() - started
            after = {c: cpu(c) for c in before}
            replay(path)
            resource = {
                c: {
                    "average_cores": (after[c]["usage_usec"] - before[c]["usage_usec"])
                    / elapsed
                    / 1e6,
                    "throttled_wall_fraction": (
                        after[c]["throttled_usec"] - before[c]["throttled_usec"]
                    )
                    / elapsed
                    / 1e6,
                }
                for c in before
            }
            healthy = qualifies(result, rate, resource)
            record = {
                "rate": rate,
                "seed": declaration["seeds"][index],
                "healthy": bool(healthy),
                "cpu": resource,
                "cpu_before": before,
                "cpu_after": after,
                "elapsed_seconds": elapsed,
                "directory": path.name,
                "slo_screen": {
                    name: {
                        cohort: {
                            "bad": ledger[bad],
                            "requests": ledger[total],
                            "wilson_upper_99": wilson(ledger[bad], ledger[total], z=SCREEN_Z)[1],
                            "ceiling": SCREEN_CEILINGS[name],
                        }
                        for cohort, bad, total in (
                            ("treatment", "total_bad", "treatment_requests"),
                            ("control", "control_bad", "control_requests"),
                        )
                    }
                    for name, ledger in result["ledgers"].items()
                },
            }
            records.append(record)
            atomic_json(directory / "calibration.json", records)
            if not healthy:
                raise RuntimeError("sustained qualification failed; no comparison study started")
            state["completed_qualifications"] += 1
            atomic_json(status, state | {"updated_utc": now()})
        stop.set()
        worker.join(timeout=12)
        if measurement_hashes != {
            str(p.relative_to(ROOT)): file_sha256(p) for p in measurement_paths
        }:
            raise RuntimeError("measurement code changed during qualification; new freeze required")
        if (
            environment() != qualified_environment
            or runtime_fingerprint(IstioFault()) != qualified_runtime
        ):
            raise RuntimeError("runtime or packages changed before evaluation freeze")
        atomic_json(
            directory / "selected-loads.json",
            {
                "low_rps": 32,
                "high_rps": 64,
                "basis": declaration,
                "limitation": "Validated conservative workloads, not maximum capacity or production guarantees",
            },
        )
        frozen = prepare(
            study,
            directory / "selected-loads.json",
            ROOT / "results/raw/revision-cost-abort-01",
            ROOT / "results/raw/revision-cost-delay-01",
        )
        matrix = json.loads((study / "matrix.json").read_text())
        matrix.update(resource_context=True, qualification_protocol=declaration)
        for name in ("matrix.json", "plan.json"):
            atomic_json(study / name, matrix)
        evidence = study / "recovery-evidence"
        evidence.mkdir()
        for name in ("full-study-v3", "full-study-v4"):
            previous = ROOT / "results/raw" / name
            destination = evidence / name
            destination.mkdir()
            for path in previous.iterdir():
                if path.is_file() and not path.is_symlink():
                    shutil.copy2(path, destination / path.name)
            for job in json.loads((previous / "matrix.json").read_text())["jobs"]:
                if (previous / job["id"]).exists():
                    shutil.copytree(previous / job["id"], destination / job["id"])
        shutil.copytree(ROOT / "results/raw/stall-stack-diagnosis-01", evidence / "stack-diagnosis")
        for name in (
            "sustained-qualification-01",
            "sustained-qualification-02",
            "high-load-diagnosis-01",
            "high-load-fault-diagnosis-01",
        ):
            shutil.copytree(ROOT / "results/raw" / name, evidence / name)
        shutil.copytree(
            ROOT / "results/raw/full-study-v4/recovery-evidence", evidence / "v4-recovery-context"
        )
        state.update(
            state="STUDY_RUNNING",
            main_study_running=True,
            directory=str(study),
            status_path=str(study / "status.json"),
            frozen_source=str(frozen),
        )
        atomic_json(status, state | {"updated_utc": now()})
        # Use the newly frozen runner for all comparison observations.
        env = os.environ.copy() | {"PYTHONPATH": str(frozen / "src")}
        with (study / "driver.log").open("ab") as log:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "cc_cep.study",
                    "execute",
                    "--directory",
                    str(study),
                ],
                cwd=frozen,
                env=env,
                stdout=log,
                stderr=log,
            )
            returncode = child.wait()
        state.update(
            state="STUDY_EXITED_REVIEW_STATUS",
            main_study_running=False,
            returncode=returncode,
        )
        atomic_json(status, state | {"updated_utc": now()})
        desktop_notice(
            "Study process exited. Review active-study.json and the verified results before submission.",
            directory,
        )
    except BaseException as exc:
        atomic_json(
            status,
            state
            | {
                "state": "STOPPED_FOR_DIAGNOSIS",
                "main_study_running": False,
                "error": repr(exc),
                "updated_utc": now(),
            },
        )
        (directory / "pipeline-error.txt").write_text(traceback.format_exc())
        desktop_notice(
            "Study stopped: " + repr(exc) + ". Evidence was retained; check active-study.json.",
            directory,
        )
        raise
    finally:
        stop.set()
        worker.join(timeout=12)


if __name__ == "__main__":
    main()
