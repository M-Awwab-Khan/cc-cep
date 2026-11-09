"""No-fault client capacity calibration on the dedicated test cluster."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import numpy as np

from cc_cep.evidence import snapshot_source
from cc_cep.istio import IstioFault
from cc_cep.runtime import RunLock
from cc_cep.smoke import port

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot_source(args.output)
    base = [
        str(ROOT / ".tools/bin/kubectl"),
        "--kubeconfig",
        str(ROOT / "kubeconfig.local"),
        "--context",
        "kind-cc-cep",
        "-n",
        "cc-cep",
    ]
    processes, logs, urls, rows = [], [], [], []
    with RunLock(ROOT / "results/tmp/cluster-controller.lock"):
        adapter = IstioFault()
        adapter.clear()
        assert not adapter.active()
        try:
            for cohort in ("control", "treatment"):
                local = port()
                urls.append(f"http://127.0.0.1:{local}")
                log = (args.output / f"{cohort}.log").open("w")
                logs.append(log)
                processes.append(
                    subprocess.Popen(
                        [
                            *base,
                            "port-forward",
                            f"service/frontend-{cohort}",
                            f"{local}:8000",
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
                                raise
                            time.sleep(0.1)
            for rate in (80, 160, 320, 640, 960):
                raw = (args.output / f"rate-{rate}.jsonl").resolve()
                with (args.output / f"rate-{rate}.log").open("w") as log:
                    result = subprocess.run(
                        [
                            str(ROOT / ".tools/bin/k6"),
                            "run",
                            "--out",
                            f"json={raw}",
                            str(ROOT / "experiments/load.js"),
                        ],
                        env=os.environ
                        | {
                            "CONTROL_URL": urls[0],
                            "TREATMENT_URL": urls[1],
                            "RPS": str(rate),
                            "DURATION": "15s",
                            "SEED": "11",
                            "BACKGROUND": "0",
                        },
                        stdout=log,
                        stderr=log,
                        timeout=50,
                    )
                outcomes = {c: [] for c in ("control", "treatment")}
                durations = []
                dropped = 0
                for line in raw.read_text().splitlines():
                    item = json.loads(line)
                    if item.get("type") != "Point":
                        continue
                    data = item["data"]
                    metric = item["metric"]
                    if metric == "cc_outcome":
                        outcomes[data["tags"]["cohort"]].append(data["value"])
                    if metric == "http_req_duration":
                        durations.append(data["value"])
                    if metric == "dropped_iterations":
                        dropped += data["value"]
                record = {
                    "rps_per_cohort": rate,
                    "exit_code": result.returncode,
                    "dropped": dropped,
                    "p95_ms": float(np.quantile(durations, 0.95)) if durations else None,
                    "cohorts": {
                        c: {
                            "total": len(v),
                            "availability_bad": sum(x == 2 for x in v),
                            "latency_bad": sum(x != 0 for x in v),
                        }
                        for c, v in outcomes.items()
                    },
                }
                record["healthy"] = (
                    result.returncode == 0
                    and dropped == 0
                    and all(
                        x["total"] >= rate * 14
                        and x["availability_bad"] / x["total"] <= 0.01
                        and x["latency_bad"] / x["total"] <= 0.05
                        for x in record["cohorts"].values()
                    )
                )
                rows.append(record)
                (args.output / "calibration.json").write_text(json.dumps(rows, indent=2) + "\n")
                print(json.dumps(record), flush=True)
                if not record["healthy"]:
                    break
        finally:
            for proc in processes:
                proc.terminate()
                proc.wait(timeout=5)
            for log in logs:
                log.close()
    healthy = [r["rps_per_cohort"] for r in rows if r["healthy"]]
    if not healthy:
        raise RuntimeError("no healthy load level found")
    result = {
        "tested_healthy_ceiling": max(healthy),
        "low_rps": round(0.3 * max(healthy)),
        "high_rps": round(0.7 * max(healthy)),
        "limitation": "15-second engineering calibration; tested ceiling is not a universal capacity estimate",
    }
    (args.output / "selected-loads.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
