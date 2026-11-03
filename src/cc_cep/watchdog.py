"""Run independently of the experiment controller; bounded lifetime then cleanup."""

import argparse
import math
import signal
import time

from .istio import PREFIX, IstioFault, safe_spec


def step(adapter):
    resource = adapter.inspect()
    now = adapter.clock()
    expires = float(resource["metadata"].get("annotations", {}).get(PREFIX + "expires", 0))
    active = any("fault" in route for route in resource["spec"].get("http", []))
    if active and (not math.isfinite(expires) or not expires or now >= expires):
        adapter.patch(resource, safe_spec(), {PREFIX + "expires": "0"})
        adapter.beat(now)
        return "expired fault removed"
    adapter.beat(now)
    return "heartbeat"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()
    if not 0 < args.seconds <= 3600:
        parser.error("watchdog duration must be finite, in (0, 3600]")
    adapter = IstioFault()
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    deadline = time.monotonic() + args.seconds
    consecutive_failures = 0
    try:
        while not stopped and time.monotonic() < deadline:
            try:
                message = step(adapter)
                consecutive_failures = 0
                if message != "heartbeat":
                    print(message, flush=True)
            except Exception as exc:
                consecutive_failures += 1
                # Optimistic writes may race a renewal. Retry; stale heartbeat blocks admission.
                print(f"WATCHDOG ERROR: {exc}", flush=True)
                if consecutive_failures >= 3:
                    try:
                        adapter.clear()
                    except Exception as cleanup:
                        print(f"CLEANUP ERROR: {cleanup}", flush=True)
            time.sleep(0.5)
    finally:
        adapter.clear()
        if adapter.active():
            raise RuntimeError("watchdog cleanup unverified")


if __name__ == "__main__":
    main()
