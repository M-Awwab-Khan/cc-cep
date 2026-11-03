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
from .istio import IstioFault
from .runtime import RunLock, checkpoint
from .smoke import port


class OutcomeReader:
    def __init__(self, path):
        self.stream = Path(path).open()
        self.counts = {"control": [0, 0, 0], "treatment": [0, 0, 0]}
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


def run(config_path: Path, isolation: Path, output: Path):
    root = Path(__file__).resolve().parents[2]
    data = json.loads(config_path.read_text())
    config_data = dict(data["controller"])
    config_data["slos"] = tuple(SLO(**item) for item in config_data["slos"])
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
    adapter = IstioFault(family=data["family"])
    controller = Controller(config)
    run_id = str(uuid.uuid4())
    processes, logs, reader = [], [], None
    metadata = {
        "schema": 1,
        "mode": "cluster-pilot",
        "run_id": run_id,
        "created_utc": time.time(),
        "config": data,
        "isolation_sha256": hashlib.sha256(isolation.read_bytes()).hexdigest(),
        "uv_lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "src").rglob("*.py"))
        },
        "exposure_definition": "API-acknowledged intensity integral, includes removal latency; xDS propagation remains uncertain",
        "limitations": [
            "shared Kubernetes node",
            "pilot, not frozen evaluation",
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
            return proc

        watchdog = spawn(
            [
                sys.executable,
                "-m",
                "cc_cep.watchdog",
                "--seconds",
                str(min(3600, warmup + config.duration + 60)),
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
                "DURATION": str(int(warmup + config.duration + 10)) + "s",
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
        if min(reader.latest.values()) < now - config.max_age:
            raise RuntimeError("stale baseline client telemetry")
        # Counts are aligned by one ingestion boundary. Per-cohort latest points are freshness gates.
        initial = controller.admit(Snapshot(now, run_id, *counts), now)
        if emergency.exists():
            raise RuntimeError("emergency stop requested")
        checkpoint(output / "checkpoint.json", controller)
        adapter.apply(initial, ttl=6)
        last_applied, last_actuation = initial, time.monotonic()
        with (output / "events.jsonl").open("w") as events:
            while controller.state == State.RUNNING:
                time.sleep(interval)
                counts = reader.read()
                now = time.time()
                adapter.inspect()
                heartbeat = adapter.last_watchdog
                if emergency.exists():
                    controller.stop("manual emergency stop")
                elif load.poll() is not None or watchdog.poll() is not None:
                    controller.failed = True
                    controller.stop("load/watchdog process exited")
                elif now - min(reader.latest.values()) > config.max_age or now - heartbeat > 2:
                    controller.failed = True
                    controller.stop("stale client telemetry or watchdog")
                else:
                    controller.tick(Snapshot(now, run_id, *counts), now)
                checkpoint(output / "checkpoint.json", controller)
                tick_time = time.monotonic()
                exposure += last_applied * (tick_time - last_actuation)
                last_actuation = tick_time
                event = {
                    "snapshot": asdict(Snapshot(now, run_id, *counts)),
                    "state": controller.state,
                    "reason": controller.reason,
                    "next_intensity": controller.intensity,
                    "ledgers": {k: asdict(v) for k, v in controller.ledgers.items()},
                }
                events.write(json.dumps(event) + "\n")
                events.flush()
                if controller.state == State.RUNNING:
                    adapter.apply(controller.intensity, ttl=6)
                    acknowledged = time.monotonic()
                    exposure += last_applied * (acknowledged - last_actuation)
                    last_applied, last_actuation = controller.intensity, acknowledged
        # No fault renewal after STOPPING. Stop and verify cleanup before terminating the watcher.
        controller.cleanup(adapter)
        exposure += last_applied * (time.monotonic() - last_actuation)
        last_applied = 0
    except BaseException as exc:
        controller.failed = True
        controller.stop(f"run failed: {exc}")
        raise
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        if reader:
            try:
                if controller.last is not None:
                    tail = reader.read()
                    now = time.time()
                    controller.account_tail(Snapshot(now, run_id, *tail), now)
            except (ValueError, ArithmeticError) as exc:
                controller.failed = True
                controller.reason += f"; tail accounting failed: {exc}"
            reader.close()
        for log in logs:
            log.close()
        clean = controller.cleanup(adapter)
        if last_applied:
            exposure += last_applied * (time.monotonic() - last_actuation)
        controller.state = State.COMPLETE if clean and not controller.failed else State.FAILED
        checkpoint(output / "checkpoint.json", controller)
        summary = {
            "mode": "cluster-pilot",
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
        }
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
        checks = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.is_file()
        }
        (output / "checksums.json").write_text(json.dumps(checks, indent=2))
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
