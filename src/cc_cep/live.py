"""Client-observed closed-loop cluster pilot. Must pass the isolation spike first.

k6 writes a raw point for each eligible outcome. No interpolated Prometheus rates enter
request-count ledgers. The watchdog is an independent process with a bounded lifetime.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import httpx

from .core import SLO, Config, Controller, Counts, Snapshot, State
from .evidence import seal, snapshot_source
from .istio import IstioFault
from .runtime import RunLock, checkpoint, process_token
from .smoke import port


class OutcomeReader:
    def __init__(self, path):
        self.stream = Path(path).open()
        self.counts = {"control": [0, 0, 0], "treatment": [0, 0, 0]}
        self.organic = {"control": 0, "treatment": 0}
        self.latest = {"control": 0.0, "treatment": 0.0}

    def read(self):
        while True:
            position = self.stream.tell()
            line = self.stream.readline()
            if not line:
                break
            if not line.endswith("\n"):
                self.stream.seek(position)
                break
            item = json.loads(line)
            if (
                item.get("type") == "Point"
                and item.get("metric") == "dropped_iterations"
                and item["data"]["value"] > 0
            ):
                raise ValueError("load generator dropped eligible iterations")
            if item.get("type") != "Point" or item.get("metric") != "cc_outcome":
                continue
            data = item["data"]
            cohort = data["tags"]["cohort"]
            value = data["value"]
            if cohort not in self.counts or value not in (0, 1, 2):
                raise ValueError("invalid client outcome")
            self.organic[cohort] += int(data["tags"].get("organic") == "1")
            count = self.counts[cohort]
            count[0] += 1
            count[1] += int(value == 2)
            count[2] += int(value != 0)
            self.latest[cohort] = max(
                self.latest[cohort],
                datetime.fromisoformat(data["time"].replace("Z", "+00:00")).timestamp(),
            )
        return [Counts(*self.counts[cohort]) for cohort in ("control", "treatment")]

    def close(self):
        self.stream.close()


def cluster_inventory(adapter):
    pods = adapter._run("get", "pods", "-l", "cohort", "-o", "json")["items"]
    return sorted(
        [
            {
                "name": pod["metadata"]["name"],
                "uid": pod["metadata"]["uid"],
                "containers": sorted(
                    [
                        {
                            "name": c["name"],
                            "image_id": c.get("imageID"),
                            "ready": c.get("ready"),
                            "restarts": c.get("restartCount"),
                        }
                        for c in (
                            pod["status"].get("containerStatuses", [])
                            + [
                                c
                                for c in pod["status"].get("initContainerStatuses", [])
                                if c["name"] == "istio-proxy"
                            ]
                        )
                    ],
                    key=lambda c: c["name"],
                ),
            }
            for pod in pods
        ],
        key=lambda p: p["name"],
    )


def stop_process(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def fresh_clients(latest, now, max_age):
    return all(0 <= now - timestamp <= max_age for timestamp in latest.values())


def shutdown_workloads(controller, adapter, processes, watchdog):
    """Remove faults before shutdown; keep the independent guardian through draining."""
    clean = controller.cleanup(adapter)
    for proc in reversed(processes):
        if proc is not watchdog:
            stop_process(proc)
    return clean


def run(config_path: Path, isolation: Path, output: Path):
    root = Path(__file__).resolve().parents[2]
    data = json.loads(config_path.read_text())
    config_data = dict(data["controller"])
    config_data["slos"] = tuple(SLO(**item) for item in config_data["slos"])
    config_data.setdefault(
        "expected_fault_requests", int(data["rps_per_cohort"] * config_data["duration"])
    )
    config = Config(**config_data)
    rps, interval, warmup = data["rps_per_cohort"], data["interval_seconds"], data["warmup_seconds"]
    if not 0 < rps <= config.max_rps or not 0 < interval <= config.max_age or warmup <= 0:
        raise ValueError("invalid load/cadence")
    # Account for the full watchdog TTL, observation interval, client timeout, and API margin.
    if config.reserve_seconds < 6 + interval + 2 + 5:
        raise ValueError("reserve must cover TTL + interval + client timeout + API margin")
    proof = json.loads(isolation.read_text())
    if (
        proof.get("mode") != "cluster-integration"
        or not proof.get("passed")
        or not proof.get("cleanup_verified")
    ):
        raise ValueError("successful cluster isolation/cleanup evidence required")
    if not 0 <= time.time() - proof["created_utc"] < 3600:
        raise ValueError("repeat isolation check; evidence older than one hour")
    output.mkdir(parents=True, exist_ok=False)
    snapshot_source(output)
    (output / "events.jsonl").touch()
    adapter = IstioFault(family=data["family"])
    controller = Controller(config)
    run_id = str(uuid.uuid4())
    processes, logs, reader = [], [], None
    watchdog = None
    process_records = []
    metadata = {
        "schema": 2,
        "python": sys.version,
        "mode": data.get("mode", "cluster-pilot"),
        "run_id": run_id,
        "created_utc": time.time(),
        "config": data,
        "effective_controller": asdict(config),
        "accounting_version": "realized-cumulative-v2",
        "telemetry_clock_version": "post-inspection-v1",
        "isolation_sha256": hashlib.sha256(isolation.read_bytes()).hexdigest(),
        "uv_lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "src").rglob("*.py"))
        },
        "exposure_definition": "API-acknowledged intensity integral, includes removal latency; xDS propagation remains uncertain",
        "limitations": [
            "shared Kubernetes node",
            "engineering pilot"
            if data.get("mode", "cluster-pilot") == "cluster-pilot"
            else "predeclared laboratory comparison",
            "Istio fault RNG is not seeded by workload seed",
        ],
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    started = time.monotonic()
    exposure = 0.0
    last_applied = 0.0
    last_actuation = started
    lock_path = root / "results/tmp/cluster-controller.lock"
    emergency = root / "results/tmp/EMERGENCY_STOP"
    lock = RunLock(lock_path)
    lock.__enter__()  # A rejected competing run must never clean up the owner's fault.
    try:
        initial_inventory = cluster_inventory(adapter)
        (output / "cluster-before.json").write_text(json.dumps(initial_inventory, indent=2))
        if len(initial_inventory) != 4 or any(
            {c["name"] for c in p["containers"]} != {"app", "istio-proxy"}
            or not all(c["ready"] for c in p["containers"])
            for p in initial_inventory
        ):
            raise RuntimeError("benchmark pods are not fully ready")
        # A restart never re-applies saved intensity. Verify clear before any new admission.
        adapter.clear()
        if adapter.active():
            raise RuntimeError("preflight fault removal unverified")

        def spawn(command, name, env=None, independent=False):
            log = (output / f"{name}.log").open("w")
            logs.append(log)
            proc = subprocess.Popen(
                command, env=env, stdout=log, stderr=log, start_new_session=independent
            )
            processes.append(proc)
            process_records.append(
                {"pid": proc.pid, "name": name, "start_token": process_token(proc.pid)}
            )
            (output / "processes.json").write_text(
                json.dumps(
                    {
                        "owner_pid": os.getpid(),
                        "owner_token": process_token(os.getpid()),
                        "children": process_records,
                    },
                    indent=2,
                )
            )
            return proc

        watchdog = spawn(
            [
                sys.executable,
                "-m",
                "cc_cep.watchdog",
                "--seconds",
                str(min(3600, warmup + config.duration + data.get("recovery_seconds", 0) + 60)),
            ],
            "watchdog",
            independent=True,
        )
        urls = []
        for cohort in ("control", "treatment"):
            local_port = port()
            urls.append(f"http://127.0.0.1:{local_port}")
            spawn(
                [
                    str(root / ".tools/bin/kubectl"),
                    "--kubeconfig",
                    str(root / "kubeconfig.local"),
                    "--context",
                    "kind-cc-cep",
                    "-n",
                    "cc-cep",
                    "port-forward",
                    f"service/frontend-{cohort}",
                    f"{local_port}:8000",
                    "--address",
                    "127.0.0.1",
                ],
                f"port-forward-{cohort}",
            )
        with httpx.Client(timeout=1, trust_env=False) as client:
            for url in urls:
                deadline = time.monotonic() + 15
                while True:
                    try:
                        client.get(url + "/health").raise_for_status()
                        break
                    except httpx.HTTPError:
                        if time.monotonic() > deadline:
                            raise RuntimeError("port-forward unavailable") from None
                        time.sleep(0.1)
        raw = output / "k6.jsonl"
        raw.touch()
        load = spawn(
            [
                str(root / ".tools/bin/k6"),
                "run",
                "--out",
                f"json={raw.resolve()}",
                str(root / "experiments/load.js"),
            ],
            "k6",
            env=os.environ
            | {
                "CONTROL_URL": urls[0],
                "TREATMENT_URL": urls[1],
                "RPS": str(rps),
                "SEED": str(data.get("workload_seed", 0)),
                "BACKGROUND": str(data.get("background_probability", 0)),
                "CONTROL_BACKGROUND": str(
                    data.get(
                        "control_background_probability", data.get("background_probability", 0)
                    )
                ),
                "DURATION": str(int(warmup + config.duration + data.get("recovery_seconds", 0) + 5))
                + "s",
            },
        )
        reader = OutcomeReader(raw)
        deadline = time.monotonic() + warmup
        while time.monotonic() < deadline:
            if load.poll() is not None or watchdog.poll() is not None or emergency.exists():
                raise RuntimeError("warmup interrupted")
            time.sleep(0.2)
        counts = reader.read()
        now = time.time()
        if not fresh_clients(reader.latest, now, config.max_age):
            raise RuntimeError("stale baseline client telemetry")
        # Counts are aligned by one ingestion boundary. Per-cohort latest points are freshness gates.
        (output / "baseline.json").write_text(
            json.dumps(asdict(Snapshot(now, run_id, *counts)), indent=2)
        )
        organic_baseline = dict(reader.organic)
        (output / "baseline-organic.json").write_text(json.dumps(organic_baseline))
        initial = controller.admit(
            Snapshot(now, run_id, *counts, isolation_ok=not data.get("contaminated", False)), now
        )
        if emergency.exists():
            raise RuntimeError("emergency stop requested")
        checkpoint(output / "checkpoint.json", controller)
        if not data.get("no_fault", False):
            adapter.apply(
                initial, ttl=6, telemetry_deadline=min(reader.latest.values()) + config.max_age
            )
        else:
            initial = 0
            controller.intensity = 0
        last_applied, last_actuation = initial, time.monotonic()
        with (output / "events.jsonl").open("w") as events:
            while controller.state == State.RUNNING:
                time.sleep(interval)
                counts = reader.read()
                now = time.time()
                adapter.inspect()
                decision_time = time.time()
                heartbeat = adapter.last_watchdog
                if emergency.exists():
                    controller.failed = True
                    controller.stop("manual emergency stop")
                elif load.poll() is not None or watchdog.poll() is not None:
                    controller.failed = True
                    controller.stop("load/watchdog process exited")
                elif (
                    not fresh_clients(reader.latest, decision_time, config.max_age)
                    or not 0 <= decision_time - heartbeat <= 2
                ):
                    controller.failed = True
                    controller.stop("stale client telemetry or watchdog")
                else:
                    controller.tick(
                        Snapshot(
                            now, run_id, *counts, isolation_ok=not data.get("contaminated", False)
                        ),
                        decision_time,
                    )
                if data.get("no_fault", False):
                    controller.intensity = 0
                checkpoint(output / "checkpoint.json", controller)
                tick_time = time.monotonic()
                exposure += last_applied * (tick_time - last_actuation)
                last_actuation = tick_time
                event = {
                    "decision_timestamp": decision_time,
                    "client_latest": dict(reader.latest),
                    "watchdog_timestamp": heartbeat,
                    "snapshot": asdict(Snapshot(now, run_id, *counts)),
                    "state": controller.state,
                    "reason": controller.reason,
                    "next_intensity": controller.intensity,
                    "ledgers": {k: asdict(v) for k, v in controller.ledgers.items()},
                }
                events.write(json.dumps(event) + "\n")
                events.flush()
                if controller.state == State.RUNNING and not data.get("no_fault", False):
                    adapter.apply(
                        controller.intensity,
                        ttl=6,
                        telemetry_deadline=min(reader.latest.values()) + config.max_age,
                    )
                    acknowledged = time.monotonic()
                    exposure += last_applied * (acknowledged - last_actuation)
                    last_applied, last_actuation = controller.intensity, acknowledged
        # No fault renewal after STOPPING. Stop and verify cleanup before terminating the watcher.
        controller.cleanup(adapter)
        exposure += last_applied * (time.monotonic() - last_actuation)
        last_applied = 0
        recovery_end = (
            time.monotonic()
            + max(0, config.duration - (time.time() - controller.started))
            + data.get("recovery_seconds", 0)
        )
        while time.monotonic() < recovery_end:
            if emergency.exists():
                controller.reason += "; emergency during recovery"
                break
            time.sleep(max(0, min(0.2, recovery_end - time.monotonic())))
        if load.wait(timeout=12) != 0:
            raise RuntimeError("load generator exited unsuccessfully")
    except BaseException as exc:
        controller.failed = True
        controller.stop(f"run failed: {type(exc).__name__}: {exc}")
        raise
    finally:
        cleared_before_drain = shutdown_workloads(controller, adapter, processes, watchdog)
        if cleared_before_drain and last_applied:
            exposure += last_applied * (time.monotonic() - last_actuation)
            last_applied = 0
        if reader:
            try:
                if controller.last is not None:
                    tail = reader.read()
                    now = time.time()
                    controller.account_tail(Snapshot(now, run_id, *tail), now)
                    with (output / "events.jsonl").open("a") as events:
                        events.write(
                            json.dumps(
                                {
                                    "phase": "cleanup-tail",
                                    "snapshot": asdict(controller.last),
                                    "state": controller.state,
                                    "reason": controller.reason,
                                    "next_intensity": 0,
                                    "ledgers": {
                                        k: asdict(v) for k, v in controller.ledgers.items()
                                    },
                                }
                            )
                            + "\n"
                        )
            except (ValueError, ArithmeticError) as exc:
                controller.failed = True
                controller.reason += f"; tail accounting failed: {exc}"
            reader.close()
        for log in logs:
            log.close()
        try:
            final_inventory = cluster_inventory(adapter)
            (output / "cluster-after.json").write_text(json.dumps(final_inventory, indent=2))
            if "initial_inventory" in locals() and final_inventory != initial_inventory:
                controller.failed = True
                controller.reason += "; benchmark identity/readiness changed during run"
        except Exception as exc:
            controller.failed = True
            controller.reason += f"; final cluster inventory unavailable: {exc}"
        clean = controller.cleanup(adapter)
        if clean and watchdog is not None:
            stop_process(watchdog)
            if watchdog.returncode != 0:
                controller.failed = True
                controller.reason += "; watchdog exited unsuccessfully"
            clean = controller.cleanup(adapter)
        if last_applied:
            exposure += last_applied * (time.monotonic() - last_actuation)
        controller.state = State.COMPLETE if clean and not controller.failed else State.FAILED
        checkpoint(output / "checkpoint.json", controller)
        summary = {
            "mode": data.get("mode", "cluster-pilot"),
            "run_id": run_id,
            "policy": config.policy,
            "family": data["family"],
            "seed": data.get("workload_seed"),
            "state": controller.state,
            "stop_reason": controller.reason,
            "cleanup_verified": clean,
            "cleanup_errors": controller.cleanup_errors,
            "exposure_fraction_seconds": exposure,
            "ledgers": {k: asdict(v) for k, v in controller.ledgers.items()},
            "organic_after_baseline": {
                k: reader.organic[k] - organic_baseline[k] for k in reader.organic
            }
            if reader and controller.last and "organic_baseline" in locals()
            else None,
            "unsealed_files": ["watchdog.log"]
            if not clean and watchdog is not None and watchdog.poll() is None
            else [],
        }
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
        if summary["unsealed_files"]:
            (output / "watchdog-at-failure.log").write_bytes((output / "watchdog.log").read_bytes())
        seal(output, exclude=set(summary["unsealed_files"]))
        lock.__exit__(None, None, None)
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--isolation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.isolation, args.output), indent=2))
