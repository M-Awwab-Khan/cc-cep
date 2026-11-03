"""Checksum-verified summary and empirical cost oracle; no predictive guarantee."""

import csv
import hashlib
import json
from pathlib import Path


def analyze(directory: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = []
    runs = []
    for path in sorted(directory.rglob("summary.json")):
        checks = json.loads((path.parent / "checksums.json").read_text())
        for filename, expected in checks.items():
            if Path(filename).name != filename:
                raise ValueError("invalid evidence filename")
            if hashlib.sha256((path.parent / filename).read_bytes()).hexdigest() != expected:
                raise ValueError(f"evidence checksum mismatch: {path.parent / filename}")
        if not {"metadata.json", "events.jsonl", "summary.json"} <= checks.keys():
            raise ValueError("incomplete evidence manifest")
        summary = json.loads(path.read_text())
        runs.append(
            {
                k: summary.get(k)
                for k in ("run_id", "mode", "state", "stop_reason", "cleanup_verified")
            }
        )
        for name, ledger in summary["ledgers"].items():
            exposure = summary["exposure_fraction_seconds"]
            rows.append(
                {
                    "run_id": summary["run_id"],
                    "mode": summary["mode"],
                    "policy": summary["policy"],
                    "seed": summary["seed"],
                    "family": summary["family"],
                    "slo": name,
                    "signed": ledger["signed"],
                    "enforced": ledger["enforced"],
                    "allocation": ledger["allocation"],
                    "overshoot": max(0, ledger["enforced"] - ledger["allocation"]),
                    "exposure": exposure,
                    "empirical_cost_per_exposure": ledger["signed"] / exposure
                    if exposure > 0
                    else None,
                    "stop_reason": summary["stop_reason"],
                    "cleanup_verified": summary["cleanup_verified"],
                }
            )
    (directory / "run-status.json").write_text(json.dumps(runs, indent=2))
    if not rows:
        raise ValueError("no completed evidence found")
    with (directory / "analysis.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    fig, ax = plt.subplots(figsize=(8, 4))
    for policy in sorted({r["policy"] for r in rows}):
        points = [r for r in rows if r["policy"] == policy and r["slo"] == "availability"]
        ax.scatter([r["exposure"] for r in points], [r["overshoot"] for r in points], label=policy)
    ax.set(
        xlabel="Fault exposure (fraction × seconds)",
        ylabel="Enforcement overshoot (requests)",
        title=" / ".join(sorted({r["mode"] for r in rows})) + ": overshoot versus exposure",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(directory / "overshoot-exposure.png", dpi=150)
    plt.close(fig)
    return {
        "runs": len(runs),
        "failed_runs": sum(r["state"] == "FAILED" for r in runs),
        "rows": len(rows),
        "table": str(directory / "analysis.csv"),
        "plot": str(directory / "overshoot-exposure.png"),
        "limitation": "Descriptive evidence only; empirical costs are not predictions or causal guarantees.",
    }
