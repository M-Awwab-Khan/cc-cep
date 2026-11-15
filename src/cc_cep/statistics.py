"""Predeclared run-level paired analysis, with failed/missing blocks visible."""

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .evidence import verify
from .replay import replay


def paired_interval(pairs, expected_blocks, seed=20261103):
    if set(pairs) != set(expected_blocks):
        return {
            "n": len(pairs),
            "complete": False,
            "missing_blocks": sorted(set(expected_blocks) - set(pairs)),
            "mean_difference": None,
            "ci_low": None,
            "ci_high": None,
        }
    values = np.array([pairs[k] for k in sorted(pairs)], dtype=float)
    if len(values) < 2:
        return {
            "n": len(values),
            "complete": False,
            "mean_difference": float(values.mean()) if len(values) else None,
            "ci_low": None,
            "ci_high": None,
            "missing_blocks": [],
        }
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (10000, len(values)))].mean(axis=1)
    return {
        "n": len(values),
        "complete": True,
        "mean_difference": float(values.mean()),
        "ci_low": float(np.quantile(means, 0.025)),
        "ci_high": float(np.quantile(means, 0.975)),
        "missing_blocks": [],
    }


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def analyze_matrix(directory: Path):
    matrix = json.loads((directory / "matrix.json").read_text())
    trial_rows, outcomes, valid = [], [], {}
    attempts = []
    for job in matrix["jobs"]:
        for attempt in job.get("attempts", []):
            record = {
                "job": job["id"],
                **attempt,
                "selected": attempt["directory"] == job["directory"],
            }
            try:
                retained = verify(directory / attempt["directory"])
                record.update(
                    evidence_verified=True,
                    cleanup_verified=retained["cleanup_verified"],
                    reason=retained["stop_reason"],
                )
            except (OSError, ValueError, KeyError) as exc:
                record.update(evidence_verified=False, reason=str(exc))
            attempts.append(record)
    write_csv(directory / "attempts.csv", attempts)
    for job in matrix["jobs"]:
        path = directory / job["directory"]
        row = dict(job)
        try:
            summary = verify(path)
            row.update(
                state=summary["state"],
                reason=summary["stop_reason"],
                cleanup_verified=summary["cleanup_verified"],
            )
            if summary["state"] == "COMPLETE" and summary["cleanup_verified"]:
                row["replay"] = replay(path)
            else:
                row["replay"] = None
            meta = json.loads((path / "metadata.json").read_text())
            reserve = (
                meta["effective_controller"]["max_rps"]
                * meta["effective_controller"]["reserve_seconds"]
            )
            for name, ledger in summary["ledgers"].items():
                organic = (summary.get("organic_after_baseline") or {}).get("treatment")
                residual = ledger["total_bad"] - organic if organic is not None else None
                outcomes.append(
                    dict(
                        job,
                        slo=name,
                        state=summary["state"],
                        signed=ledger["signed"],
                        enforced=ledger["enforced"],
                        total_bad=ledger["total_bad"],
                        requests=ledger["treatment_requests"],
                        allocation=ledger["allocation"],
                        reserve=reserve,
                        overshoot=max(0, ledger["enforced"] - ledger["allocation"]),
                        guard_overshoot=max(
                            0, ledger["enforced"] - (ledger["allocation"] - reserve)
                        ),
                        exposure=summary["exposure_fraction_seconds"],
                        residual_reference=residual,
                        point_attribution_error=abs(ledger["signed"] - residual)
                        if residual is not None
                        else None,
                        total_accounting_error=abs(ledger["total_bad"] - residual)
                        if residual is not None
                        else None,
                    )
                )
            if row["replay"] is not None:
                valid[job["directory"]] = summary
        except (OSError, ValueError, KeyError) as exc:
            row.update(state="UNVERIFIED", reason=str(exc), cleanup_verified=False, replay=None)
        trial_rows.append(row)
    write_csv(directory / "trials.csv", trial_rows)
    write_csv(directory / "outcomes.csv", outcomes)
    groups = defaultdict(dict)
    for row in outcomes:
        if row["directory"] in valid and row["kind"] == "core":
            groups[(row["family"], row["rps"], row["slo"], row["policy"])][row["seed"]] = row
    comparisons = []
    for family in ("abort", "delay"):
        for rps in matrix["loads"]:
            for slo in ("availability", "latency"):
                closed = groups[(family, rps, slo, "closed-loop")]
                for comparator in ("static", "threshold", "open-loop"):
                    other = groups[(family, rps, slo, comparator)]
                    for metric in ("overshoot", "guard_overshoot", "exposure", "total_bad"):
                        pairs = {
                            seed: closed[seed][metric] - other[seed][metric]
                            for seed in closed.keys() & other.keys()
                        }
                        comparisons.append(
                            dict(
                                family=family,
                                rps=rps,
                                slo=slo,
                                comparator=comparator,
                                metric=metric,
                                definition="closed-loop minus comparator",
                                **paired_interval(pairs, matrix["seeds"]),
                            )
                        )
    write_csv(directory / "paired-comparisons.csv", comparisons)
    background = defaultdict(dict)
    for row in outcomes:
        if row["directory"] in valid and row["kind"] == "background":
            background[(row["rps"], row["slo"], row.get("attribution_mode", "attributed"))][
                row["seed"]
            ] = row
    bg_rows = []
    for rps in matrix["loads"]:
        for slo in ("availability", "latency"):
            attributed = background[(rps, slo, "attributed")]
            total = background[(rps, slo, "total")]
            for metric in ("guard_overshoot", "exposure", "enforced"):
                pairs = {
                    seed: attributed[seed][metric] - total[seed][metric]
                    for seed in attributed.keys() & total.keys()
                }
                bg_rows.append(
                    dict(
                        rps=rps,
                        slo=slo,
                        metric=metric,
                        definition="attributed debit mode minus total debit mode",
                        **paired_interval(pairs, matrix["seeds"]),
                    )
                )
            errors = {
                seed: row["point_attribution_error"] - row["total_accounting_error"]
                for seed, row in attributed.items()
                if row["point_attribution_error"] is not None
            }
            bg_rows.append(
                dict(
                    rps=rps,
                    slo=slo,
                    metric="absolute attribution error",
                    definition="point estimate minus naive total, on the same trial",
                    **paired_interval(errors, matrix["seeds"]),
                )
            )
    write_csv(directory / "background-comparisons.csv", bg_rows)
    oracle = []
    for group, values in sorted(groups.items()):
        costs = {
            seed: row["signed"] / row["exposure"]
            for seed, row in values.items()
            if row["exposure"] > 0
        }
        oracle.append(
            dict(
                family=group[0],
                rps=group[1],
                slo=group[2],
                policy=group[3],
                units="signed bad requests per fraction-second exposure",
                **paired_interval(costs, matrix["seeds"]),
            )
        )
    write_csv(directory / "oracle.csv", oracle)
    status = {
        "planned": len(matrix["jobs"]),
        "verified_complete": len(valid),
        "failed_or_unverified": sum(row["state"] != "COMPLETE" for row in trial_rows),
        "complete_pairs": sum(row["complete"] for row in comparisons),
        "planned_pairs": len(comparisons),
        "inference": "95% percentile bootstrap of paired independent run-block differences; 10000 resamples",
        "limitations": [
            "five replication blocks offer limited precision",
            "shared node and port forwarding constrain external validity",
            "no multiplicity adjustment; intervals are descriptive",
            "synthetic organic labels define a residual reference, not universal causal ground truth",
        ],
    }
    (directory / "statistical-summary.json").write_text(json.dumps(status, indent=2) + "\n")
    if outcomes:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        for axis, slo in zip(axes, ("availability", "latency")):
            for policy in ("static", "threshold", "open-loop", "closed-loop"):
                points = [
                    r
                    for r in outcomes
                    if r["kind"] == "core"
                    and r["slo"] == slo
                    and r["directory"] in valid
                    and r["policy"] == policy
                ]
                axis.scatter(
                    [r["exposure"] for r in points],
                    [r["guard_overshoot"] for r in points],
                    label=policy,
                    alpha=0.7,
                )
            axis.set(
                title=slo.capitalize(),
                xlabel="Command exposure (fraction-seconds)",
                ylabel="Usable-allocation overshoot (requests)",
            )
        axes[1].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(directory / "comparison.png", dpi=180)
        plt.close(fig)
    return status
