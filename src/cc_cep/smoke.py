"""Real HTTP safety validation on dynamically allocated loopback ports.

These are integration checks, not comparative research measurements. The killed worker
is an actuator lease-renewer; validating the distributed Kubernetes watchdog remains open.
"""

import asyncio
import hashlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from .core import Config, Controller, Counts, Snapshot
from .runtime import LocalFault, RunLock, checkpoint


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def batch(urls, n=120):
    # Client-observed outcomes include connection errors and timeouts.
    async with httpx.AsyncClient(
        timeout=1, trust_env=False, limits=httpx.Limits(max_connections=40)
    ) as client:
        semaphore = asyncio.Semaphore(40)

        async def request(url):
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(url + "/work")
                    failed = response.status_code >= 400
                except httpx.HTTPError:
                    failed = True
                elapsed = time.perf_counter() - started
                return int(failed), int(failed or elapsed > 0.5)

        counts = []
        for url in urls:
            outcomes = await asyncio.gather(*(request(url) for _ in range(n)))
            counts.append(Counts(n, sum(a for a, _ in outcomes), sum(b for _, b in outcomes)))
        return counts


def smoke(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    token = secrets.token_urlsafe(32)
    processes, logs = [], []
    control_port, treatment_port = port(), port()
    while treatment_port == control_port:
        treatment_port = port()
    urls = [f"http://127.0.0.1:{p}" for p in (control_port, treatment_port)]
    adapter = LocalFault(urls[1], token)
    evidence = {"mode": "local-http-integration", "checks": {}, "created_utc": time.time()}
    controller = Controller(Config())
    try:
        for cohort, server_port in zip(("control", "treatment"), (control_port, treatment_port)):
            env = os.environ | {"CC_COHORT": cohort, "CC_DEPENDENCY_URL": ""}
            env["CC_LOCAL_FAULT_TOKEN"] = token if cohort == "treatment" else ""
            log = (output / f"{cohort}.log").open("w")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "cc_cep.app:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(server_port),
                        "--no-access-log",
                    ],
                    env=env,
                    stdout=log,
                    stderr=log,
                )
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
                            raise RuntimeError("benchmark did not start") from None
                        time.sleep(0.05)
            assert (
                client.put(
                    urls[0] + "/local-fault",
                    json={"intensity": 1, "ttl": 1},
                    headers={"x-fault-token": token},
                ).status_code
                == 403
            )
        evidence["checks"]["control_rejects_fault"] = True
        baseline = asyncio.run(batch(urls))
        assert all(c.availability == 0 and c.latency == 0 for c in baseline), baseline
        evidence["checks"]["healthy_baseline"] = [asdict(c) for c in baseline]
        for family in ("abort", "delay"):
            adapter.family = family
            adapter.apply(1, ttl=5)
            counts = asyncio.run(batch(urls, 20))
            assert counts[0].availability == counts[0].latency == 0, counts
            assert (counts[1].availability if family == "abort" else counts[1].latency) == 20
            adapter.clear()
            assert not adapter.active()
            evidence["checks"][family + "_isolated_and_removed"] = [asdict(c) for c in counts]
        # Drive the actual controller with client-observed cumulative outcomes.
        controller.admit(Snapshot(time.time(), "local-http", *baseline), time.time())
        # Fault made intentionally severe to exercise automatic stop/cleanup, not tune policy.
        adapter.family = "abort"
        with RunLock(output / "target.lock"):
            checkpoint(output / "checkpoint.json", controller)
            adapter.apply(1, ttl=2)
            counts = asyncio.run(batch(urls))
            accumulated = [
                Counts(a.total + b.total, a.availability + b.availability, a.latency + b.latency)
                for a, b in zip(baseline, counts)
            ]
            now = time.time()
            controller.tick(Snapshot(now, "local-http", *accumulated), now)
            assert controller.intensity == 0
            assert controller.cleanup(adapter)
            checkpoint(output / "checkpoint.json", controller)
        evidence["checks"]["controller_stopped_and_cleanup_verified"] = controller.reason
        # Crash a separate lease-renewer. No cleanup finally block runs in this worker.
        worker = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import os,time; from cc_cep.runtime import LocalFault; "
                "a=LocalFault(os.environ['CC_URL'],os.environ['CC_TOKEN']); "
                "exec('while True:\\n a.apply(1, ttl=1)\\n time.sleep(.2)')",
            ],
            env=os.environ | {"CC_URL": urls[1], "CC_TOKEN": token},
            stdout=logs[1],
            stderr=logs[1],
        )
        processes.append(worker)
        deadline = time.monotonic() + 5
        while not adapter.active():
            if worker.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("lease worker did not start")
            time.sleep(0.05)
        worker.kill()
        worker.wait(timeout=5)
        started = time.monotonic()
        while adapter.active() and time.monotonic() - started < 2:
            time.sleep(0.05)
        assert not adapter.active(), "fault survived expiry"
        recovered = asyncio.run(batch(urls, 20))
        assert all(c.availability == c.latency == 0 for c in recovered)
        evidence["checks"]["killed_renewer_fault_expired_seconds"] = time.monotonic() - started
        evidence["checks"]["recovery"] = [asdict(c) for c in recovered]
        evidence["passed"] = True
    except BaseException as exc:
        evidence.update(passed=False, error=repr(exc))
        raise
    finally:
        try:
            adapter.clear()
            evidence["cleanup_verified"] = not adapter.active()
        except Exception as exc:
            evidence["cleanup_verified"] = False
            evidence["cleanup_error"] = repr(exc)
        for process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()
        (output / "integration.json").write_text(json.dumps(evidence, indent=2))
        hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.is_file()
        }
        (output / "checksums.json").write_text(json.dumps(hashes, indent=2))
    return evidence
