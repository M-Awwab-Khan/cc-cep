"""Seeded request-count model. Not Kubernetes measurements or a load-capacity model."""

import hashlib
import json
import random
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .core import Config, Controller, Counts, Snapshot, State


class MemoryFault:
    def __init__(self):
        self.intensity = 0

    def clear(self):
        self.intensity = 0

    def active(self):
        return self.intensity > 0


def simulate(
    config: Config, seed: int, family: str, output: Path, background=0.001, contaminated=False
):
    if family not in {"abort", "delay"} or not 0 <= background <= 1:
        raise ValueError("invalid fault model")
    output.mkdir(parents=True, exist_ok=False)
    run_id = str(uuid.uuid4())
    canonical = json.dumps(asdict(config), sort_keys=True)
    root = Path(__file__).resolve().parents[2]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    ).stdout.strip()
    sources = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "src").rglob("*.py"))
    }
    metadata = {
        "source_revision": revision,
        "source_sha256": sources,
        "python": sys.version,
        "uv_lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "schema": 1,
        "mode": "simulation",
        "run_id": run_id,
        "seed": seed,
        "family": family,
        "background": background,
        "config": asdict(config),
        "config_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "created_utc_epoch": time.time(),
        "model": "independent Bernoulli v1",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    controller = Controller(config)
    fault = MemoryFault()
    # No-fault warmup represented by baseline counts; not a measured healthy cluster.
    baseline = Counts(10000, 0, 0)
    snapshot = Snapshot(0, run_id, baseline, baseline)
    total_c, total_t = baseline, baseline
    exposure = 0.0
    try:
        fault.intensity = controller.admit(snapshot, 0)
        with (output / "events.jsonl").open("w") as stream:
            for tick in range(1, int(config.duration) + 1):
                intensity = fault.intensity
                # Independent streams keyed by seed/tick/cohort: common random numbers across policies.
                cohorts = []
                for cohort in ("control", "treatment"):
                    rng = random.Random(f"{seed}:{tick}:{cohort}")
                    n = int(config.expected_treatment_requests / config.duration)
                    bad_a = bad_l = 0
                    for _ in range(n):
                        organic, u = rng.random() < background, rng.random()
                        hit = u < intensity and (cohort == "treatment" or contaminated)
                        failed = organic or (family == "abort" and hit)
                        bad_a += int(failed)
                        bad_l += int(failed or (family == "delay" and hit))
                    cohorts.append(Counts(n, bad_a, bad_l))

                def add(a, b):
                    return Counts(
                        a.total + b.total, a.availability + b.availability, a.latency + b.latency
                    )

                total_c, total_t = add(total_c, cohorts[0]), add(total_t, cohorts[1])
                snapshot = Snapshot(
                    float(tick), run_id, total_c, total_t, isolation_ok=not contaminated
                )
                exposure += intensity
                fault.intensity = controller.tick(snapshot, tick)
                event = {
                    "snapshot": asdict(snapshot),
                    "applied_intensity": intensity,
                    "next_intensity": fault.intensity,
                    "state": controller.state,
                    "reason": controller.reason,
                    "ledgers": {k: asdict(v) for k, v in controller.ledgers.items()},
                }
                stream.write(json.dumps(event) + "\n")
                if controller.state != State.RUNNING:
                    break
    except Exception as exc:
        controller.failed = True
        controller.stop(f"execution failed: {exc}")
        raise
    finally:
        clean = controller.cleanup(fault)
        summary = {
            "mode": "simulation",
            "run_id": run_id,
            "policy": config.policy,
            "seed": seed,
            "family": family,
            "exposure_fraction_seconds": exposure,
            "cleanup_verified": clean,
            "cleanup_errors": controller.cleanup_errors,
            "state": controller.state,
            "stop_reason": controller.reason,
            "ledgers": {k: asdict(v) for k, v in controller.ledgers.items()},
        }
        if clean:
            controller.state = State.FAILED if controller.failed else State.COMPLETE
            summary["state"] = controller.state
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
        hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.is_file()
        }
        (output / "checksums.json").write_text(json.dumps(hashes, indent=2))
    return summary
