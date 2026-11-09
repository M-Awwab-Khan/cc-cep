"""Predeclared sustained baseline admission, distinct from comparison outcomes."""

from .core import wilson

SCREEN_Z = 2.5758293035489004  # Two-sided 99% Wilson screening interval, per stream.
SCREEN_CEILINGS = {"availability": 0.005, "latency": 0.025}


def qualifies(result, rate, resource):
    if result["state"] != "COMPLETE" or not result["cleanup_verified"]:
        return False
    if set(resource) != {"control", "treatment"}:
        return False
    if set(result["ledgers"]) != {"availability", "latency"}:
        return False
    for ledger in result["ledgers"].values():
        if min(ledger["treatment_requests"], ledger["control_requests"]) < rate * 400:
            return False
    # Require 50% headroom against the actual SLO bad fractions. A single organic
    # failure in tens of thousands of requests does not imply an unhealthy service.
    # This finite-sample screen is not a simultaneous or causal coverage guarantee.
    for name, ceiling in SCREEN_CEILINGS.items():
        ledger = result["ledgers"][name]
        for bad, total in (
            (ledger["total_bad"], ledger["treatment_requests"]),
            (ledger["control_bad"], ledger["control_requests"]),
        ):
            if not 0 <= bad <= total or wilson(bad, total, z=SCREEN_Z)[1] > ceiling:
                return False
    return all(
        0 <= r["average_cores"] <= 0.70 and 0 <= r["throttled_wall_fraction"] <= 0.05
        for r in resource.values()
    )
