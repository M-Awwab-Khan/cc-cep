"""Resumable full-duration study, frozen before evaluation seeds are used.

One bounded, sequential experiment job, not a recurring automation. All invalid attempts
remain in the manifest. A failed removal halts the queue before another admission.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import random
import shutil
import signal
import subprocess
import tarfile
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .cluster_smoke import smoke
from .evidence import ROOT, seal, snapshot_source, verify
from .istio import IstioFault
from .live import cluster_inventory, run
from .replay import replay
from .runtime import RunLock, process_token
from .statistics import analyze_matrix


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(temporary, path)


def runtime_fingerprint(adapter):
    """Pin benchmark templates and resolved images across the entire study."""
    inventory = cluster_inventory(adapter)
    if len(inventory) != 4 or any(
        {c["name"] for c in p["containers"]} != {"app", "istio-proxy"}
        or not all(c["ready"] for c in p["containers"])
        for p in inventory
    ):
        raise RuntimeError("benchmark runtime is not fully ready")
    fingerprint = {}
    for name in (
        "frontend-control",
        "frontend-treatment",
        "dependency-control",
        "dependency-treatment",
    ):
        deployment = adapter._run("get", "deployment", name, "-o", "json")
        template = deployment["spec"]["template"]
        pods = [p for p in inventory if p["name"].startswith(name + "-")]
        if len(pods) != 1 or any(not c["image_id"] for c in pods[0]["containers"]):
            raise RuntimeError("benchmark rollout/image identity is not stable")
        fingerprint[name] = {
            "template_sha256": hashlib.sha256(
                json.dumps(template, sort_keys=True).encode()
            ).hexdigest(),
            "images": sorted((c["name"], c["image_id"]) for c in pods[0]["containers"]),
        }
    return fingerprint


def progress(jobs):
    return {
        "completed_jobs": sum(
            bool(j["attempts"]) and j["attempts"][-1]["state"] == "COMPLETE" for j in jobs
        ),
        "attempted_jobs": sum(bool(j["attempts"]) for j in jobs),
    }


def capture_context(directory):
    """Read-only context for diagnosing transient stalls; never relaxes safety gates."""
    record = {"utc": now(), "host_load": os.getloadavg()}
    record["host_memory_kib"] = {
        line.split(":")[0]: int(line.split()[1])
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.split(":")[0] in {"MemAvailable", "SwapFree", "SwapTotal"}
    }
    commands = {
        "cluster_pods": [
            str(ROOT / ".tools/bin/kubectl"),
            "--kubeconfig",
            str(ROOT / "kubeconfig.local"),
            "--context",
            "kind-cc-cep",
            "-n",
            "cc-cep",
            "get",
            "pods",
            "-l",
            "cohort",
            "-o",
            "json",
        ],
        "node_resources": [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            "cc-cep-control-plane",
        ],
    }
    for name, command in commands.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=True)
            value = json.loads(result.stdout)
            if name == "cluster_pods":
                value = [
                    {
                        "name": p["metadata"]["name"],
                        "uid": p["metadata"]["uid"],
                        "status": p["status"],
                    }
                    for p in value["items"]
                ]
            record[name] = value
        except Exception as exc:
            record[name + "_error"] = repr(exc)
    with (directory / "resource-context.jsonl").open("a") as stream:
        stream.write(json.dumps(record) + "\n")


def config_for(rps, family, policy, seed, costs, *, kind="core", mode="attributed"):
    cap = math.ceil(1.4 * rps)
    reserve = cap * 15
    headroom = math.ceil(rps * 0.1 * 300 * 0.5)
    allocation = reserve + headroom
    expected = math.ceil(2 * allocation / 0.01) + 1
    return {
        "mode": "cluster-evaluation",
        "purpose": "Frozen laboratory study, not long-window SLO validation",
        "reservation_horizon_seconds": expected / rps,
        "family": family,
        "workload_seed": seed,
        "rps_per_cohort": rps,
        "warmup_seconds": 120,
        "recovery_seconds": 120,
        "interval_seconds": 2,
        "no_fault": kind == "control",
        "background_probability": 0.005 if kind == "background" else 0,
        "controller": {
            "slos": [
                {
                    "name": "availability",
                    "target": 0.99,
                    "allocation_fraction": allocation / (0.01 * expected),
                },
                {
                    "name": "latency",
                    "target": 0.95,
                    "allocation_fraction": allocation / (0.05 * expected),
                },
            ],
            "expected_treatment_requests": expected,
            "expected_fault_requests": rps * 300,
            "duration": 300,
            "max_age": 5,
            "min_requests": 50,
            "max_rps": cap,
            "reserve_seconds": 15,
            "max_intensity": 0.1,
            "step": 0.005,
            "severe_burn": 20,
            "policy": policy,
            "pilot_cost": costs[family],
            "short_window": 5,
            "long_window": 30,
            "cooldown": 2,
            "attribution_mode": mode,
            "background_model": "iid-bernoulli" if kind == "background" else "unvalidated",
            "uncertainty_alpha": 0.05,
        },
    }


def make_plan(loads, costs):
    seeds = list(range(1001, 1006))
    jobs = []
    rng = random.Random(20261103)
    for seed in seeds:
        block = []
        for family in ("abort", "delay"):
            for rps in loads:
                for policy in ("static", "threshold", "open-loop", "closed-loop"):
                    block.append(
                        {
                            "id": f"core-{family}-{rps}-{policy}-{seed}",
                            "kind": "core",
                            "family": family,
                            "rps": rps,
                            "policy": policy,
                            "seed": seed,
                        }
                    )
        for rps in loads:
            block.append(
                {
                    "id": f"control-{rps}-{seed}",
                    "kind": "control",
                    "family": "abort",
                    "rps": rps,
                    "policy": "closed-loop",
                    "seed": seed,
                }
            )
        rng.shuffle(block)
        jobs.extend(block)
    # Attribution ablation: same background, per-load matched replication blocks, both debit modes.
    for seed in seeds:
        block = []
        for rps in loads:
            for mode in ("attributed", "total"):
                block.append(
                    {
                        "id": f"background-{rps}-{mode}-{seed}",
                        "kind": "background",
                        "family": "abort",
                        "rps": rps,
                        "policy": "closed-loop",
                        "seed": seed,
                        "attribution_mode": mode,
                    }
                )
        rng.shuffle(block)
        jobs.extend(block)
    for job in jobs:
        job["config"] = config_for(
            job["rps"],
            job["family"],
            job["policy"],
            job["seed"],
            costs,
            kind=job["kind"],
            mode=job.get("attribution_mode", "attributed"),
        )
        job["directory"] = job["id"] + "/attempt-0"
        job["attempts"] = []
    return {
        "schema": 2,
        "created_utc": now(),
        "loads": list(loads),
        "seeds": seeds,
        "order_seed": 20261103,
        "costs": costs,
        "jobs": jobs,
        "protocol": {
            "core": 80,
            "controls": 10,
            "background_ablations": 20,
            "phase_seconds": {"warmup": 120, "fault": 300, "recovery_minimum": 120},
            "minimum_core_runtime_hours": 90 * 545 / 3600,
            "minimum_total_runtime_hours": 110 * 545 / 3600,
            "retry_rule": "At most one retry for failed execution/admission/replay, never for an unfavorable valid outcome",
            "primary_metrics": [
                "full allocation overshoot",
                "usable guard overshoot",
                "command exposure",
                "per-SLO total bad requests",
            ],
            "inference": "paired block percentile bootstrap, 10000 resamples, 95% descriptive intervals",
        },
    }


def environment():
    return {
        name: importlib.metadata.version(name)
        for name in (
            "httpx",
            "fastapi",
            "uvicorn",
            "prometheus-client",
            "numpy",
            "matplotlib",
            "pyyaml",
        )
    }


def prepare(directory, calibration, pilot_abort, pilot_delay):
    directory.mkdir(parents=True, exist_ok=False)
    selected = json.loads(calibration.read_text())
    costs = {}
    for family, pilot in [("abort", pilot_abort), ("delay", pilot_delay)]:
        summary = verify(pilot)
        replay(pilot)
        if summary["state"] != "COMPLETE" or not summary["cleanup_verified"]:
            raise ValueError("successful independent cost pilots required")
        meta = json.loads((pilot / "metadata.json").read_text())
        cost = max(ledger["signed"] for ledger in summary["ledgers"].values()) / (
            meta["config"]["rps_per_cohort"] * summary["exposure_fraction_seconds"]
        )
        if not math.isfinite(cost) or cost <= 0:
            raise ValueError("pilot cost is not identifiable")
        costs[family] = cost
    plan = make_plan((selected["low_rps"], selected["high_rps"]), costs)
    plan["environment"] = environment()
    plan["original_root"] = str(ROOT)
    plan["pilot_evidence"] = {
        family: {
            "path": str(p.resolve()),
            "checksums_sha256": hashlib.sha256((p / "checksums.json").read_bytes()).hexdigest(),
        }
        for family, p in [("abort", pilot_abort), ("delay", pilot_delay)]
    }
    snapshot_source(directory)
    frozen = directory / "frozen"
    frozen.mkdir()
    with tarfile.open(directory / "source.tar.gz", "r:gz") as archive:
        archive.extractall(frozen, filter="data")
    # Runtime links are deliberately outside the allowlisted source archive.
    (frozen / ".tools").symlink_to(ROOT / ".tools", target_is_directory=True)
    (frozen / "kubeconfig.local").symlink_to(ROOT / "kubeconfig.local")
    (frozen / "results").mkdir()
    (frozen / "results/tmp").symlink_to(ROOT / "results/tmp", target_is_directory=True)
    (frozen / "results/curated").mkdir()
    shutil.copy2(
        ROOT / "results/curated/study-results.tex", frozen / "results/curated/study-results.tex"
    )
    for name in ("calibration.json", "selected-loads.json"):
        shutil.copy2(calibration.parent / name, directory / name)
    inputs = directory / "input-evidence"
    inputs.mkdir()
    for name, folder in (
        ("calibration", calibration.parent),
        ("pilot-abort", pilot_abort),
        ("pilot-delay", pilot_delay),
    ):
        shutil.copytree(folder, inputs / name)
    plan["source_archive_sha256"] = hashlib.sha256(
        (directory / "source.tar.gz").read_bytes()
    ).hexdigest()
    anchor = runtime_fingerprint(IstioFault())
    atomic_json(directory / "runtime-anchor.json", anchor)
    plan["runtime_anchor"] = anchor
    atomic_json(directory / "plan.json", plan)
    atomic_json(directory / "matrix.json", plan)
    return frozen


def recover_attempt(target, job, adapter):
    if (target / "summary.json").exists():
        result = verify(target)
        if result["state"] == "COMPLETE" and result["cleanup_verified"]:
            replay(target)
            return result
    with RunLock(ROOT / "results/tmp/cluster-controller.lock"):
        records = target / "processes.json"
        record = None
        if records.exists():
            record = json.loads(records.read_text())
            if (
                record.get("owner_token")
                and process_token(record["owner_pid"]) == record["owner_token"]
            ):
                raise RuntimeError("previous experiment owner is still alive")
        # Preserve any independent guardian until fault absence is verified.
        adapter.clear()
        if adapter.active():
            raise RuntimeError("cannot resume: fault removal unverified")
        if record is not None:
            for child in record["children"]:
                if child.get("start_token") and process_token(child["pid"]) == child["start_token"]:
                    try:
                        os.kill(child["pid"], signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            time.sleep(2)
            for child in record["children"]:
                if child.get("start_token") and process_token(child["pid"]) == child["start_token"]:
                    try:
                        os.kill(child["pid"], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
    if (target / "summary.json").exists():
        return json.loads((target / "summary.json").read_text())
    if not (target / "metadata.json").exists():
        (target / "metadata.json").write_text(
            json.dumps({"mode": "interrupted-setup", "config": job["config"]})
        )
    (target / "events.jsonl").touch(exist_ok=True)
    saved = (
        json.loads((target / "checkpoint.json").read_text())
        if (target / "checkpoint.json").exists()
        else {}
    )
    result = {
        "state": "FAILED",
        "cleanup_verified": True,
        "stop_reason": "interrupted; complete tail unavailable",
        "run_id": job["id"],
        "policy": job["policy"],
        "family": job["family"],
        "seed": job["seed"],
        "mode": "cluster-evaluation",
        "data_complete": False,
        "exposure_fraction_seconds": None,
        "ledgers": saved.get("ledgers", {}),
    }
    (target / "summary.json").write_text(json.dumps(result, indent=2))
    seal(target)
    return result


def execute(directory):
    matrix = json.loads((directory / "matrix.json").read_text())
    status = {
        "state": "STARTING",
        "pid": os.getpid(),
        "started_utc": now(),
        **progress(matrix["jobs"]),
        "planned_jobs": len(matrix["jobs"]),
        "active_job": None,
    }
    stop = threading.Event()
    mutex = threading.Lock()

    def persist(**changes):
        with mutex:
            status.update(changes, heartbeat_utc=now())
            atomic_json(directory / "status.json", status)

    def heartbeat():
        ticks = 0
        while not stop.wait(15):
            persist()
            ticks += 1
            if matrix.get("resource_context") and ticks % 2 == 0:
                try:
                    capture_context(directory)
                except Exception as exc:
                    persist(context_error=repr(exc))

    worker = threading.Thread(target=heartbeat, daemon=True)
    owner = RunLock(ROOT / "results/tmp/study-driver.lock")
    owner.__enter__()
    worker.start()

    def terminate(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, terminate)
    adapter = IstioFault()
    try:
        proof = None
        for job in matrix["jobs"]:
            if shutil.disk_usage(directory).free < 10 * 1024**3:
                raise RuntimeError("less than 10 GiB free; queue halted before another injection")
            if environment() != matrix["environment"]:
                raise RuntimeError("dependency environment changed after freeze")
            if matrix.get("runtime_anchor"):
                # JSON round-trip normalizes tuple image pairs to lists.
                current = json.loads(json.dumps(runtime_fingerprint(adapter)))
                if current != matrix["runtime_anchor"]:
                    raise RuntimeError("benchmark template or resolved images changed after freeze")
            if job["attempts"] and job["attempts"][-1].get("state") == "COMPLETE":
                replay(directory / job["directory"])
                continue
            persist(state="RUNNING", active_job=job["id"])
            result = {"state": "FAILED", "cleanup_verified": not adapter.active()}
            attempt_limit = job.get("max_attempts", 2)
            for attempt in range(len(job["attempts"]), attempt_limit):
                if (
                    proof is None
                    or time.time() - json.loads(proof.read_text())["created_utc"] > 2700
                ):
                    safety_dir = directory / f"safety-{int(time.time())}"
                    smoke(safety_dir)
                    proof = safety_dir / "integration.json"
                target = directory / job["id"] / f"attempt-{attempt}"
                config = directory / (job["id"] + ".json")
                config.write_text(json.dumps(job["config"], indent=2) + "\n")
                started = now()
                if target.exists():
                    result = recover_attempt(target, job, adapter)
                    job["directory"] = str(target.relative_to(directory))
                    job["attempts"].append(
                        {
                            "attempt": attempt,
                            "directory": job["directory"],
                            "started_utc": started,
                            "finished_utc": now(),
                            "state": result["state"],
                            "error": "recovered interrupted driver",
                        }
                    )
                    atomic_json(directory / "matrix.json", matrix)
                    if result["state"] == "COMPLETE":
                        break
                    continue
                error = None
                try:
                    result = run(config, proof, target)
                    if result["state"] == "COMPLETE":
                        replay(target)
                except Exception as exc:
                    error = repr(exc)
                    (directory / f"{job['id']}-attempt-{attempt}-error.txt").write_text(
                        traceback.format_exc()
                    )
                    result = (
                        json.loads((target / "summary.json").read_text())
                        if (target / "summary.json").exists()
                        else {"state": "FAILED", "cleanup_verified": not adapter.active()}
                    )
                if error:
                    result["state"] = "FAILED"
                job["directory"] = str(target.relative_to(directory))
                job["attempts"].append(
                    {
                        "attempt": attempt,
                        "directory": job["directory"],
                        "started_utc": started,
                        "finished_utc": now(),
                        "state": result["state"],
                        "error": error,
                    }
                )
                atomic_json(directory / "matrix.json", matrix)
                if not result["cleanup_verified"] or adapter.active():
                    raise RuntimeError("cleanup unverified: study halted before next injection")
                if result["state"] == "COMPLETE":
                    break
                if attempt + 1 < attempt_limit:
                    time.sleep(30)
                    proof = None
            counts = progress(matrix["jobs"])
            completed = counts["completed_jobs"]
            persist(**counts)
            print(
                json.dumps(
                    {
                        "finished": job["id"],
                        "state": result["state"],
                        "completed": completed,
                        "planned": len(matrix["jobs"]),
                        "utc": now(),
                    }
                ),
                flush=True,
            )
            if result["state"] != "COMPLETE":
                raise RuntimeError(
                    "trial exhausted invalid-execution retries; queue halted for diagnosis"
                )
        persist(state="ANALYZING", active_job=None)
        analysis = analyze_matrix(directory)
        atomic_json(directory / "analysis-completion.json", analysis)
        persist(
            state="ANALYSIS_COMPLETE"
            if analysis["failed_or_unverified"] == 0
            else "INCOMPLETE_DATA",
            analysis=analysis,
        )
        # Publication/report rendering is a separate audited stage; never declare CEP complete here.
        from .study_report import build_report

        build_report(directory, Path(matrix["original_root"]))
        report_compiled = json.loads((directory / "report-status.json").read_text())["compiled"]
        persist(
            state="REPORT_BUILD_FAILED_REVIEW_REQUIRED"
            if not report_compiled
            else "ARTIFACTS_BUILT_REVIEW_REQUIRED"
            if analysis["failed_or_unverified"] == 0
            else "INCOMPLETE_DATA_REVIEW_REQUIRED",
            dataset_complete=analysis["failed_or_unverified"] == 0,
        )
    except BaseException as exc:
        persist(state="STOPPED", error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        stop.set()
        worker.join(timeout=12)
        owner.__exit__(None, None, None)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("prepare")
    new.add_argument("--directory", type=Path, required=True)
    new.add_argument("--calibration", type=Path, required=True)
    new.add_argument("--pilot-abort", type=Path, required=True)
    new.add_argument("--pilot-delay", type=Path, required=True)
    resume = sub.add_parser("execute")
    resume.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print(
            prepare(args.directory.resolve(), args.calibration, args.pilot_abort, args.pilot_delay)
        )
    else:
        execute(args.directory.resolve())


if __name__ == "__main__":
    main()
