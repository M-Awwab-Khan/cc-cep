"""One-off completion record for the already launched independent reproduction.

This never touches measurement data. It compares regenerated tables after the verifier
exits and records a failed check explicitly if it cannot substantiate completion.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    record = json.loads((ROOT / "results/curated/portable-reproduction-process.json").read_text())
    proc = Path("/proc") / str(record["pid"])
    deadline = time.monotonic() + 7200
    while proc.exists() and time.monotonic() < deadline:
        try:
            if "scripts/reproduce_evidence.py" not in (proc / "cmdline").read_text():
                break
        except FileNotFoundError:
            break
        time.sleep(15)
    original = ROOT / "results/raw/full-study-v7"
    extracted = ROOT / "results/tmp/independent-reproduction-v7-complete/study"
    log = Path(record["log"]).read_text()
    results = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "archive_manifests_verified": "Archives verified; 173 evidence manifests verified" in log,
        "verifier_reported_main_analysis_complete": any(
            line.startswith('{"planned": 110, "verified_complete": 110,')
            for line in log.splitlines()
        ),
        "traceback_present": "Traceback (most recent call last)" in log,
        "tables": {},
    }
    for name in (
        "trials.csv", "attempts.csv", "outcomes.csv", "paired-comparisons.csv",
        "background-comparisons.csv", "oracle.csv", "statistical-summary.json",
    ):
        target = extracted / name
        results["tables"][name] = {
            "sha256": digest(target) if target.exists() else None,
            "matches_original": target.exists() and digest(target) == digest(original / name),
        }
    results["passed"] = (
        results["archive_manifests_verified"]
        and results["verifier_reported_main_analysis_complete"]
        and not results["traceback_present"]
        and all(row["matches_original"] for row in results["tables"].values())
    )
    (ROOT / "results/curated/portable-reproduction-result.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    final = ROOT / "results/curated/final-deliverables.json"
    data = json.loads(final.read_text())
    data["portable_analysis_reproduction"] = "PASSED" if results["passed"] else "FAILED_REVIEW_REQUIRED"
    data["portable_reproduction_result"] = "results/curated/portable-reproduction-result.json"
    final.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
