#!/usr/bin/env python3
"""Create/delete ONLY the project-owned local kind cluster, never current-context."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".tools/bin"


def run(binary, *args):
    subprocess.run([str(BIN / binary), *args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "deploy", "delete"])
    args = parser.parse_args()
    if args.action == "create":
        # Host memory check is deliberately conservative, Docker VM allocation alone is insufficient.
        mem = {
            line.split(":")[0]: int(line.split()[1])
            for line in Path("/proc/meminfo").read_text().splitlines()
        }
        if mem["MemAvailable"] < 8 * 1024 * 1024:
            raise SystemExit("Need >=8 GiB host MemAvailable before provisioning the mesh lab")
        run(
            "kind",
            "create",
            "cluster",
            "--name",
            "cc-cep",
            "--config",
            "deploy/kind.yaml",
            "--kubeconfig",
            str(ROOT / "kubeconfig.local"),
            "--wait",
            "180s",
        )
        run(
            "istioctl",
            "--kubeconfig",
            str(ROOT / "kubeconfig.local"),
            "--context",
            "kind-cc-cep",
            "install",
            "--set",
            "profile=minimal",
            "--set",
            "tag=1.31.3",
            "-y",
        )
    elif args.action == "deploy":
        run("kind", "load", "docker-image", "cc-cep:0.1.0", "--name", "cc-cep")
        run(
            "kubectl",
            "--kubeconfig",
            str(ROOT / "kubeconfig.local"),
            "--context",
            "kind-cc-cep",
            "apply",
            "-f",
            "deploy/benchmark.yaml",
        )
        run(
            "kubectl",
            "--kubeconfig",
            str(ROOT / "kubeconfig.local"),
            "--context",
            "kind-cc-cep",
            "-n",
            "cc-cep",
            "wait",
            "--for=condition=available",
            "deployment",
            "--all",
            "--timeout=180s",
        )
        run(
            "kubectl",
            "--kubeconfig",
            str(ROOT / "kubeconfig.local"),
            "--context",
            "kind-cc-cep",
            "apply",
            "-f",
            "deploy/observability.yaml",
        )
    else:
        run("kind", "delete", "cluster", "--name", "cc-cep")


if __name__ == "__main__":
    main()
