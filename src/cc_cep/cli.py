import argparse
import json
import random
import sys
from dataclasses import replace
from pathlib import Path

from .core import Config
from .simulation import simulate


def main():
    parser = argparse.ArgumentParser(description="CC-CEP: simulation and local validation")
    sub = parser.add_subparsers(dest="command", required=True)
    sim = sub.add_parser("simulate")
    sim.add_argument("--output", type=Path, required=True)
    sim.add_argument("--seed", type=int, default=1)
    sim.add_argument(
        "--policy",
        choices=["static", "threshold", "open-loop", "closed-loop", "paced"],
        default="closed-loop",
    )
    sim.add_argument("--family", choices=["abort", "delay"], default="abort")
    matrix = sub.add_parser("matrix", help="80 model runs; not final empirical evaluation")
    matrix.add_argument("--output", type=Path, required=True)
    matrix.add_argument("--order-seed", type=int, default=20261103)
    smoke = sub.add_parser("smoke", help="real loopback HTTP and controller-death lease check")
    smoke.add_argument("--output", type=Path, required=True)
    report = sub.add_parser("analyze")
    report.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "simulate":
        print(
            json.dumps(
                simulate(Config(policy=args.policy), args.seed, args.family, args.output), indent=2
            )
        )
    elif args.command == "matrix":
        args.output.mkdir(parents=True, exist_ok=False)
        rng = random.Random(args.order_seed)
        jobs = []
        for seed in range(101, 106):
            block = [
                (policy, family, rps, seed)
                for policy in ("static", "threshold", "open-loop", "closed-loop")
                for family in ("abort", "delay")
                for rps in (150, 250)
            ]
            rng.shuffle(block)
            jobs.extend(block)
        (args.output / "order.json").write_text(json.dumps(jobs, indent=2))
        # Keep failures and continue the matrix; each trial's directory is retained.
        failures = []
        for index, (policy, family, rps, seed) in enumerate(jobs):
            cfg = replace(Config(), policy=policy, expected_treatment_requests=rps * 300)
            try:
                simulate(cfg, seed, family, args.output / f"run-{index:03}")
            except Exception as exc:
                failures.append({"index": index, "error": repr(exc)})
        (args.output / "failures.json").write_text(json.dumps(failures, indent=2))
        print(f"{len(jobs)} simulation trials, {len(failures)} execution failures: {args.output}")
        if failures:
            sys.exit(1)
    elif args.command == "smoke":
        from .smoke import smoke

        print(json.dumps(smoke(args.output), indent=2))
    elif args.command == "analyze":
        from .analysis import analyze

        print(json.dumps(analyze(args.directory), indent=2))


if __name__ == "__main__":
    main()
