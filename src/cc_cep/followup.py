"""Post-result follow-up: budget-paced closed loop, separate from the frozen v7 comparison.

The v7 analysis showed that the original closed-loop policy was limited by SRE burn-rate
gates (bad fraction / q) rather than by its budget. The paced policy replaces those gates
with consumption relative to the remaining usable allocation. Because this change was made
after seeing v7 results, it is evaluated as a separate, time-separated follow-up and is
never pooled into the frozen randomized comparison.
"""

import argparse
import csv
import hashlib
import json
import random
import tarfile
from collections import defaultdict
from pathlib import Path

from .evidence import ROOT, snapshot_source, verify
from .istio import IstioFault
from .replay import replay
from .statistics import paired_interval, write_csv
from .study import atomic_json, config_for, environment, now, runtime_fingerprint

SEEDS = list(range(1001, 1006))
ORDER_SEED = 20261115


def make_plan(loads, costs):
    rng = random.Random(ORDER_SEED)
    jobs = []
    for seed in SEEDS:
        block = [
            {
                "id": f"paced-{family}-{rps}-{seed}",
                "kind": "core",
                "family": family,
                "rps": rps,
                "policy": "paced",
                "seed": seed,
            }
            for family in ("abort", "delay")
            for rps in loads
        ]
        rng.shuffle(block)
        jobs.extend(block)
    for job in jobs:
        job["config"] = config_for(job["rps"], job["family"], "paced", job["seed"], costs)
        job["config"]["mode"] = "cluster-followup"
        job["config"]["purpose"] = "Post-result follow-up, not part of the frozen v7 comparison"
        job["directory"] = job["id"] + "/attempt-0"
        job["attempts"] = []
    return {
        "schema": 2,
        "followup": True,
        "created_utc": now(),
        "loads": list(loads),
        "seeds": SEEDS,
        "order_seed": ORDER_SEED,
        "costs": costs,
        "jobs": jobs,
        "protocol": {
            "runs": len(jobs),
            "phase_seconds": {"warmup": 120, "fault": 300, "recovery_minimum": 120},
            "retry_rule": "At most one retry for failed execution/admission/replay, never for an unfavorable valid outcome",
            "comparison": "Time-separated: paced runs vs frozen v7 runs with the same block identifiers. Not randomized together; drift between collection dates is a threat.",
            "unchanged": "Loads, SLOs, allocations, reserve, caps, step, cooldown, windows and all common guards are identical to v7.",
        },
    }


def prepare(directory: Path, base: Path):
    directory.mkdir(parents=True, exist_ok=False)
    base_plan = json.loads((base / "plan.json").read_text())
    plan = make_plan(base_plan["loads"], base_plan["costs"])
    plan["environment"] = environment()
    plan["original_root"] = str(ROOT)
    plan["base_study"] = {
        "path": str(base.resolve()),
        "plan_sha256": hashlib.sha256((base / "plan.json").read_bytes()).hexdigest(),
    }
    snapshot_source(directory)
    frozen = directory / "frozen"
    frozen.mkdir()
    with tarfile.open(directory / "source.tar.gz", "r:gz") as archive:
        archive.extractall(frozen, filter="data")
    (frozen / ".tools").symlink_to(ROOT / ".tools", target_is_directory=True)
    (frozen / "kubeconfig.local").symlink_to(ROOT / "kubeconfig.local")
    (frozen / "results").mkdir()
    (frozen / "results/tmp").symlink_to(ROOT / "results/tmp", target_is_directory=True)
    plan["source_archive_sha256"] = hashlib.sha256(
        (directory / "source.tar.gz").read_bytes()
    ).hexdigest()
    anchor = runtime_fingerprint(IstioFault())
    plan["runtime_anchor"] = anchor
    plan["runtime_matches_v7"] = json.loads(json.dumps(anchor)) == base_plan.get("runtime_anchor")
    atomic_json(directory / "runtime-anchor.json", anchor)
    atomic_json(directory / "plan.json", plan)
    atomic_json(directory / "matrix.json", plan)
    return frozen


def _rows(directory: Path, matrix):
    rows = []
    for job in matrix["jobs"]:
        path = directory / job["directory"]
        if not (path / "checksums.json").exists():
            rows.append(dict(job_id=job["id"], state="MISSING", valid=False))
            continue
        summary = verify(path)
        if summary["state"] != "COMPLETE" or not summary["cleanup_verified"]:
            rows.append(dict(job_id=job["id"], state=summary["state"], valid=False))
            continue
        replay(path)
        meta = json.loads((path / "metadata.json").read_text())
        reserve = meta["effective_controller"]["max_rps"] * meta["effective_controller"]["reserve_seconds"]
        events = [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]
        intensities = [e["next_intensity"] for e in events if "phase" not in e]
        for name, ledger in summary["ledgers"].items():
            usable = ledger["allocation"] - reserve
            rows.append(
                dict(
                    job_id=job["id"],
                    valid=True,
                    family=job["family"],
                    rps=job["rps"],
                    seed=job["seed"],
                    policy=job["policy"],
                    slo=name,
                    state=summary["state"],
                    stop_reason=summary["stop_reason"],
                    total_bad=ledger["total_bad"],
                    enforced=ledger["enforced"],
                    allocation=ledger["allocation"],
                    usable=usable,
                    usable_spent_fraction=ledger["enforced"] / usable,
                    overshoot=max(0, ledger["enforced"] - ledger["allocation"]),
                    guard_overshoot=max(0, ledger["enforced"] - usable),
                    exposure=summary["exposure_fraction_seconds"],
                    max_intensity=max(intensities, default=0),
                    bad_per_exposure=ledger["total_bad"] / summary["exposure_fraction_seconds"]
                    if summary["exposure_fraction_seconds"]
                    else None,
                )
            )
    return rows


def _base_rows(base: Path):
    rows = []
    with (base / "outcomes.csv").open() as stream:
        for row in csv.DictReader(stream):
            if row["kind"] != "core" or row["state"] != "COMPLETE":
                continue
            usable = float(row["allocation"]) - float(row["reserve"])
            exposure = float(row["exposure"])
            rows.append(
                dict(
                    family=row["family"],
                    rps=int(row["rps"]),
                    seed=int(row["seed"]),
                    policy=row["policy"],
                    slo=row["slo"],
                    total_bad=float(row["total_bad"]),
                    enforced=float(row["enforced"]),
                    usable_spent_fraction=float(row["enforced"]) / usable,
                    guard_overshoot=float(row["guard_overshoot"]),
                    exposure=exposure,
                    bad_per_exposure=float(row["total_bad"]) / exposure if exposure else None,
                )
            )
    return rows


def analyze(directory: Path, base: Path):
    matrix = json.loads((directory / "matrix.json").read_text())
    rows = _rows(directory, matrix)
    write_csv(directory / "followup-outcomes.csv", rows)
    valid = [r for r in rows if r.get("valid")]
    combined = valid + _base_rows(base)
    groups = defaultdict(dict)
    for r in combined:
        groups[(r["family"], r["rps"], r["slo"], r["policy"])][r["seed"]] = r
    comparisons = []
    for family in ("abort", "delay"):
        for rps in matrix["loads"]:
            for slo in ("availability", "latency"):
                paced = groups[(family, rps, slo, "paced")]
                for comparator in ("closed-loop", "open-loop", "static", "threshold"):
                    other = groups[(family, rps, slo, comparator)]
                    for metric in (
                        "guard_overshoot",
                        "exposure",
                        "total_bad",
                        "usable_spent_fraction",
                    ):
                        pairs = {
                            seed: paced[seed][metric] - other[seed][metric]
                            for seed in paced.keys() & other.keys()
                        }
                        comparisons.append(
                            dict(
                                family=family,
                                rps=rps,
                                slo=slo,
                                comparator=comparator,
                                metric=metric,
                                definition="paced (follow-up) minus v7 comparator, same block id, time-separated",
                                **paired_interval(pairs, matrix["seeds"]),
                            )
                        )
    write_csv(directory / "followup-comparisons.csv", comparisons)
    means = []
    for (family, rps, slo, policy), values in sorted(groups.items()):
        if not values:
            continue
        def mean(key):
            return sum(v[key] for v in values.values()) / len(values)

        means.append(
            dict(
                family=family,
                rps=rps,
                slo=slo,
                policy=policy,
                n=len(values),
                total_bad=mean("total_bad"),
                guard_overshoot=mean("guard_overshoot"),
                exposure=mean("exposure"),
                usable_spent_fraction=mean("usable_spent_fraction"),
            )
        )
    write_csv(directory / "followup-means.csv", means)
    status = {
        "planned": len(matrix["jobs"]),
        "valid": len({r["job_id"] for r in valid}),
        "invalid": sorted({r["job_id"] for r in rows if not r.get("valid")}),
        "complete_pairs": sum(c["complete"] for c in comparisons),
        "planned_pairs": len(comparisons),
        "limitations": [
            "post-result policy change; evaluated separately from frozen v7",
            "time-separated pairing with v7 block ids; not jointly randomized",
            "five blocks, descriptive bootstrap intervals, no multiplicity adjustment",
        ],
    }
    atomic_json(directory / "followup-summary.json", status)
    return status


def _fmt(value, digits):
    return f"${value:.{digits}f}$"


def write_table(directory: Path, output: Path):
    """LaTeX table of latency-ledger means and paired differences, generated from CSVs."""
    with (directory / "followup-means.csv").open() as stream:
        means = {
            (r["family"], int(r["rps"]), r["policy"]): r
            for r in csv.DictReader(stream)
            if r["slo"] == "latency"
        }
    with (directory / "followup-comparisons.csv").open() as stream:
        pairs = {
            (r["family"], int(r["rps"]), r["comparator"], r["metric"]): r
            for r in csv.DictReader(stream)
            if r["slo"] == "latency"
        }

    def diff(key):
        r = pairs[key]
        if r["complete"] != "True":
            return "incomplete"
        return (
            f"{_fmt(float(r['mean_difference']), 2)} "
            f"[{_fmt(float(r['ci_low']), 2)}, {_fmt(float(r['ci_high']), 2)}]"
        )

    lines = [
        r"\begin{table*}[width=\textwidth,cols=7,pos=t]",
        r"\caption{Budget-paced follow-up over five blocks. Guard overshoot is in requests and exposure in fraction-seconds, on the latency ledger (an abort counts against both ledgers, so abort values are the same for availability). Means for paced runs, and paced minus v7 differences with 95\% block-bootstrap intervals. The pairing is time-separated, not jointly randomized.}\label{tbl:followup}",
        r"\footnotesize",
        r"\begin{tabular*}{\tblwidth}{@{\extracolsep{\fill}}llrrrll@{}}",
        r"\toprule",
        r"Fault & Req/s & Guard overshoot & Exposure & Usable spent & $\Delta$ exposure vs.\ closed-loop & $\Delta$ exposure vs.\ open-loop \\",
        r"\midrule",
    ]
    for family in ("abort", "delay"):
        for rps in sorted({k[1] for k in means}):
            m = means[(family, rps, "paced")]
            lines.append(
                f"{family} & {rps} & {float(m['guard_overshoot']):.1f} & "
                f"{float(m['exposure']):.2f} & {100 * float(m['usable_spent_fraction']):.0f}\\% & "
                f"{diff((family, rps, 'closed-loop', 'exposure'))} & "
                f"{diff((family, rps, 'open-loop', 'exposure'))} \\\\"
            )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table*}", ""]
    output.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("prepare")
    new.add_argument("--directory", type=Path, required=True)
    new.add_argument("--base", type=Path, required=True)
    done = sub.add_parser("analyze")
    done.add_argument("--directory", type=Path, required=True)
    done.add_argument("--base", type=Path, required=True)
    table = sub.add_parser("table")
    table.add_argument("--directory", type=Path, required=True)
    table.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.directory.resolve(), args.base.resolve()))
    elif args.command == "table":
        write_table(args.directory.resolve(), args.output)
    else:
        print(json.dumps(analyze(args.directory.resolve(), args.base.resolve()), indent=2))


if __name__ == "__main__":
    main()
