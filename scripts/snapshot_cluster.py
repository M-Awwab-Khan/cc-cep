"""Capture non-secret cluster/runtime provenance and observability health."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx

from cc_cep.smoke import port

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = [
        str(ROOT / ".tools/bin/kubectl"),
        "--kubeconfig",
        str(ROOT / "kubeconfig.local"),
        "--context",
        "kind-cc-cep",
        "-n",
        "cc-cep",
    ]

    def get(*command):
        return json.loads(subprocess.check_output([*base, *command, "-o", "json"], text=True))

    pods = get("get", "pods")["items"]
    report = {
        "created_utc": time.time(),
        "version": get("version"),
        "pods": [
            {
                "name": p["metadata"]["name"],
                "uid": p["metadata"]["uid"],
                "containers": [
                    {
                        "name": c["name"],
                        "image": c["image"],
                        "imageID": c.get("imageID"),
                        "ready": c.get("ready"),
                    }
                    for c in p["status"].get("containerStatuses", [])
                ],
            }
            for p in pods
        ],
    }
    for service, remote, path in [
        ("prometheus", 9090, "/api/v1/targets"),
        ("grafana", 3000, "/api/health"),
    ]:
        local = port()
        with (ROOT / "results/tmp" / f"{service}-inspect.log").open("w") as log:
            proc = subprocess.Popen(
                [
                    *base,
                    "port-forward",
                    f"service/{service}",
                    f"{local}:{remote}",
                    "--address",
                    "127.0.0.1",
                ],
                stdout=log,
                stderr=log,
            )
            try:
                deadline = time.monotonic() + 15
                with httpx.Client(timeout=2, trust_env=False) as client:
                    while True:
                        try:
                            response = client.get(f"http://127.0.0.1:{local}" + path)
                            response.raise_for_status()
                            report[service] = response.json()
                            break
                        except httpx.HTTPError:
                            if time.monotonic() > deadline:
                                raise
                            time.sleep(0.1)
            finally:
                proc.terminate()
                proc.wait(timeout=5)
    targets = report["prometheus"]["data"]["activeTargets"]
    if len(targets) != 4 or any(t["health"] != "up" for t in targets):
        raise RuntimeError("expected four healthy benchmark scrape targets")
    if report["grafana"].get("database") != "ok":
        raise RuntimeError("Grafana health failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("All six deployments ready; four Prometheus targets up; Grafana healthy")


if __name__ == "__main__":
    main()
