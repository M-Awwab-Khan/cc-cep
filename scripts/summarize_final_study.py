"""Derive final report/deck data from the sealed study's exported analysis tables."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/raw/full-study-v7"


def read(name):
    with (STUDY / (name + ".csv")).open() as stream:
        return list(csv.DictReader(stream))


def main():
    status = json.loads((STUDY / "statistical-summary.json").read_text())
    assert status["verified_complete"] == 110 and status["complete_pairs"] == 96
    rows, attempts = read("outcomes"), read("attempts")
    groups = defaultdict(list)
    for row in rows:
        if row["kind"] == "core" and row["slo"] == "latency":
            groups[(row["family"], int(row["rps"]), row["policy"])].append(row)
    aggregates = []
    for (family, rate, policy), values in sorted(groups.items()):
        assert len(values) == 5
        aggregates.append(
            {"family": family, "rps": rate, "policy": policy, "n": len(values)}
            | {
                name: mean(float(row[name]) for row in values)
                for name in ("total_bad", "guard_overshoot", "overshoot", "exposure")
            }
        )
    controls = [row for row in rows if row["kind"] == "control"]
    assert len(controls) == 20
    assert all(float(row["total_bad"]) == float(row["enforced"]) == 0 for row in controls)
    failed = [row for row in attempts if row["state"] != "COMPLETE"]
    assert len(attempts) == 111 and len(failed) == 1
    assert all(row["cleanup_verified"] == "True" for row in attempts)
    assert all(float(row["overshoot"]) == 0 for row in rows)
    payload = {
        "study": STUDY.name,
        "selected_runs": 110,
        "retained_attempts": len(attempts),
        "failed_attempts": len(failed),
        "full_allocation_overshoot_max": 0,
        "no_fault_controls_zero_bad_and_debit": 10,
        "core_latency_slo_means": aggregates,
        "paired": read("paired-comparisons"),
        "background": read("background-comparisons"),
        "exposure_unit": "fraction-seconds of API-acknowledged commanded injection",
        "limitations": status["limitations"],
    }
    target = ROOT / "results/curated/final-study-summary.json"
    target.write_text(json.dumps(payload, indent=2) + "\n")
    table = r"""\begin{table*}[width=\textwidth,cols=6,pos=t]
\caption{Means across five blocks for the latency ledger. Exposure is integrated commanded fault fraction in fraction-seconds. Abort failures are also latency-bad, so their availability and latency counts coincide. Full-allocation overshoot was zero for every selected run.}\label{tbl:means}
\small
\begin{tabular*}{\tblwidth}{@{\extracolsep{\fill}}lllr rr@{}}
\toprule
Fault & Requests/s & Policy & Bad requests & Guard overshoot & Exposure \\
\midrule
"""
    for row in aggregates:
        table += (
            f"{row['family']} & {row['rps']} & {row['policy']} & "
            f"{row['total_bad']:.1f} & {row['guard_overshoot']:.1f} & "
            f"{row['exposure']:.2f} \\\\\n"
        )
    table += "\\bottomrule\n\\end{tabular*}\n\\end{table*}\n"
    (ROOT / "results/curated/study-means.tex").write_text(table)
    print(target)


if __name__ == "__main__":
    main()
