"""Kill the actual live controller and verify independent watchdog removal on the lab."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from cc_cep.istio import IstioFault

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    adapter = IstioFault()
    children = []
    report = {"mode": "controller-crash-integration", "created_utc": time.time()}
    with (args.output / "controller.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "cc_cep.live",
                "--config",
                str(ROOT / "experiments/cluster-pilot.json"),
                "--isolation",
                str(args.isolation),
                "--output",
                str(args.output / "interrupted-run"),
            ],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 30
            events = args.output / "interrupted-run/events.jsonl"
            while not events.exists() or not events.stat().st_size:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("controller did not reach active loop")
                time.sleep(0.2)
            assert adapter.active()
            children = [
                int(pid)
                for pid in Path(f"/proc/{process.pid}/task/{process.pid}/children")
                .read_text()
                .split()
            ]
            started = time.monotonic()
            process.kill()  # SIGKILL: no controller finally/cleanup executes.
            process.wait(timeout=5)
            deadline = started + 12
            while adapter.active() and time.monotonic() < deadline:
                time.sleep(0.2)
            assert not adapter.active(), "independent watchdog did not remove the fault"
            report.update(
                passed=True,
                controller_exit=process.returncode,
                fault_removed_after_kill_seconds=time.monotonic() - started,
            )
        except BaseException as exc:
            report.update(passed=False, error=repr(exc))
            raise
        finally:
            if process.poll() is None:
                children = [
                    int(pid)
                    for pid in Path(f"/proc/{process.pid}/task/{process.pid}/children")
                    .read_text()
                    .split()
                ]
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for pid in children:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            # Watchdog SIGTERM clears before exit; allow its own bounded handler to finish.
            time.sleep(1)
            adapter.clear()
            report["cleanup_verified"] = not adapter.active()
            (args.output / "crash-check.json").write_text(json.dumps(report, indent=2) + "\n")
            checks = {
                str(p.relative_to(args.output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in args.output.rglob("*")
                if p.is_file()
            }
            (args.output / "checksums.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
