"""Disposable-cluster isolation/readback/expiry spike, not comparative evaluation."""

import asyncio
import hashlib
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from .istio import IstioFault
from .runtime import RunLock
from .smoke import batch, port


def wait_outcome(url, failure, timeout=10):
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=2, trust_env=False) as client:
        while time.monotonic() < deadline:
            response = client.get(url + "/work")
            if (response.status_code >= 400) == failure:
                return
            time.sleep(0.1)
    raise RuntimeError("Envoy did not reach expected fault state")


def smoke(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    adapter = IstioFault()
    processes, logs = [], []
    evidence = {
        "mode": "cluster-integration",
        "checks": {},
        "created_utc": time.time(),
        "context": "kind-cc-cep",
        "namespace": "cc-cep",
        "limitation": "Separate pods/services, shared node; no causal guarantee.",
    }
    lock = RunLock(root / "results/tmp/cluster-controller.lock")
    lock.__enter__()
    try:
        urls = []
        for cohort in ("control", "treatment"):
            local_port = port()
            urls.append(f"http://127.0.0.1:{local_port}")
            log = (output / f"port-forward-{cohort}.log").open("w")
            logs.append(log)
            processes.append(
                subprocess.Popen(
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
                    stdout=log,
                    stderr=log,
                )
            )
        with httpx.Client(timeout=2, trust_env=False) as client:
            for url in urls:
                deadline = time.monotonic() + 15
                while True:
                    try:
                        client.get(url + "/health").raise_for_status()
                        break
                    except httpx.HTTPError:
                        if time.monotonic() > deadline:
                            raise RuntimeError("port-forward failed") from None
                        time.sleep(0.1)
        log = (output / "watchdog.log").open("w")
        logs.append(log)
        watchdog = subprocess.Popen(
            [sys.executable, "-m", "cc_cep.watchdog", "--seconds", "120"], stdout=log, stderr=log
        )
        processes.append(watchdog)
        deadline = time.monotonic() + 10
        while True:
            try:
                adapter.apply(0, ttl=5)
                break
            except RuntimeError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        healthy = asyncio.run(batch(urls, 20))
        assert all(c.availability == c.latency == 0 for c in healthy), healthy
        evidence["checks"]["baseline_healthy"] = True
        for family in ("abort", "delay"):
            adapter.family = family
            adapter.apply(1, ttl=10)
            # xDS propagation is asynchronous; readback alone is insufficient.
            if family == "abort":
                wait_outcome(urls[1], True)
            else:
                time.sleep(1)
            outcomes = asyncio.run(batch(urls, 20))
            assert outcomes[0].availability == outcomes[0].latency == 0, outcomes
            assert (outcomes[1].availability if family == "abort" else outcomes[1].latency) == 20
            evidence["checks"][family + "_treatment_only"] = [c.__dict__ for c in outcomes]
            started = time.monotonic()
            # Retrying here is safe: resourceVersion conflicts never imply successful removal.
            for attempt in range(3):
                try:
                    adapter.clear()
                    break
                except subprocess.CalledProcessError:
                    if attempt == 2:
                        raise
            assert not adapter.active()
            wait_outcome(urls[1], False)
            evidence["checks"][family + "_api_cleanup_seconds"] = time.monotonic() - started
        # Stop renewing the fault and let the independent process expire it.
        adapter.family = "abort"
        applied = time.monotonic()
        adapter.apply(1, ttl=3)
        wait_outcome(urls[1], True)
        started = time.monotonic()
        deadline = started + 10
        while adapter.active() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert not adapter.active()
        assert time.monotonic() - applied >= 2.8, "fault removed before its lease expired"
        wait_outcome(urls[1], False)
        evidence["checks"]["unrenewed_fault_expired_seconds"] = time.monotonic() - started
        recovered = asyncio.run(batch(urls, 20))
        assert all(c.availability == c.latency == 0 for c in recovered), recovered
        evidence["checks"]["recovery_healthy"] = True
        evidence["passed"] = True
    except BaseException as exc:
        evidence.update(passed=False, error=repr(exc))
        raise
    finally:
        # Terminate watcher first so it cannot race the final cleanup write.
        for process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()
        try:
            adapter.clear()
            evidence["cleanup_verified"] = not adapter.active()
        except Exception as exc:
            evidence.update(cleanup_verified=False, cleanup_error=repr(exc))
        (output / "integration.json").write_text(json.dumps(evidence, indent=2))
        checks = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.is_file()
        }
        (output / "checksums.json").write_text(json.dumps(checks, indent=2))
        lock.__exit__(None, None, None)
    return evidence


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.output), indent=2))
