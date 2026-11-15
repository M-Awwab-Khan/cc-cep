"""Reconstruct v2 ledgers from retained observations and reconcile client raw counts."""

import json
import math
from pathlib import Path

from .core import SLO, Config, Controller, Counts, Snapshot
from .evidence import verify
from .live import OutcomeReader, fresh_clients


def snapshot(data):
    return Snapshot(
        data["timestamp"],
        data["epoch"],
        Counts(**data["control"]),
        Counts(**data["treatment"]),
        data.get("isolation_ok", True),
    )


def verify_decision_clock(event, max_age):
    decision = event["decision_timestamp"]
    if not fresh_clients(event["client_latest"], decision, max_age):
        raise ValueError("stale/future client telemetry at decision")
    if not 0 <= decision - event["watchdog_timestamp"] <= 2:
        raise ValueError("stale/future guardian heartbeat at decision")
    if not 0 <= decision - event["snapshot"]["timestamp"] <= max_age:
        raise ValueError("observation stale/future at decision")


def replay(directory: Path):
    summary = verify(directory)
    metadata = json.loads((directory / "metadata.json").read_text())
    if metadata.get("accounting_version") != "realized-cumulative-v2":
        raise ValueError("historical accounting version: verify hashes; do not replay with v2")
    config = dict(metadata["effective_controller"])
    config["slos"] = tuple(SLO(**slo) for slo in config["slos"])
    controller = Controller(Config(**config))
    baseline = snapshot(json.loads((directory / "baseline.json").read_text()))
    controller.admit(baseline, baseline.timestamp)
    intervals = 0
    for line in (directory / "events.jsonl").read_text().splitlines():
        event = json.loads(line)
        if (
            metadata.get("telemetry_clock_version") == "post-inspection-v1"
            and event.get("phase") != "cleanup-tail"
        ):
            verify_decision_clock(event, controller.config.max_age)
        observation = snapshot(event["snapshot"])
        controller.account_tail(observation, observation.timestamp)
        for name, ledger in controller.ledgers.items():
            for key, value in ledger.__dict__.items():
                if not math.isclose(
                    value, event["ledgers"][name][key], rel_tol=1e-10, abs_tol=1e-8
                ):
                    raise ValueError(f"ledger replay mismatch: {directory} {name}/{key}")
        intervals += 1
    if {key: ledger.__dict__ for key, ledger in controller.ledgers.items()} != summary["ledgers"]:
        raise ValueError("summary does not match replayed ledgers")
    reader = OutcomeReader(directory / "k6.jsonl")
    try:
        control, treatment = reader.read()
        for ledger in controller.ledgers.values():
            if treatment.total - baseline.treatment.total != ledger.treatment_requests:
                raise ValueError("raw treatment outcomes disagree with ledger")
            if control.total - baseline.control.total != ledger.control_requests:
                raise ValueError("raw control outcomes disagree with ledger")
    finally:
        reader.close()
    return {
        "run_id": summary["run_id"],
        "intervals_replayed": intervals,
        "raw_counts_reconciled": True,
        "state": summary["state"],
    }
