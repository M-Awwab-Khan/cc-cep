import math
from dataclasses import replace

import pytest

from cc_cep.core import SLO, Config, Controller, Counts, Snapshot, State, Unsafe, attributed
from cc_cep.runtime import RunLock, checkpoint


def base():
    return Snapshot(0, "epoch", Counts(1000, 0, 0), Counts(1000, 0, 0))


def next_snapshot(a=0, latency=0, timestamp=1, n=200):
    return Snapshot(timestamp, "epoch", Counts(1000 + n, 0, 0), Counts(1000 + n, a, latency))


def test_hand_computed_budget_and_independent_ledgers():
    controller = Controller(Config())
    controller.admit(base(), 0)
    assert controller.ledgers["availability"].allocation == pytest.approx(60)
    assert controller.ledgers["latency"].allocation == pytest.approx(300)
    controller.tick(next_snapshot(2, 10), 1)
    assert controller.ledgers["availability"].signed == 2
    assert controller.ledgers["latency"].signed == 10
    assert controller.ledgers["availability"].total_bad == 2
    assert controller.ledgers["availability"].allocation == pytest.approx(60)


def test_attribution_preserves_negative_estimate():
    signed, upper = attributed(0, 1000, 10, 1000)
    assert signed == -10
    assert upper >= 0
    assert attributed(30, 1000, 10, 1000)[0] == 20


@pytest.mark.parametrize("target", [0, 1, -1, math.nan])
def test_invalid_targets(target):
    with pytest.raises(ValueError):
        SLO("availability", target)


@pytest.mark.parametrize(
    "snapshot,now,reason",
    [
        (next_snapshot(timestamp=1), 10, "stale"),
        (next_snapshot(timestamp=2), 1, "future"),
        (next_snapshot(timestamp=0), 0, "duplicate"),
        (next_snapshot(timestamp=6), 6, "gap"),
        (replace(next_snapshot(), epoch="restart"), 1, "epoch"),
        (replace(next_snapshot(), isolation_ok=False), 1, "isolation"),
        (next_snapshot(n=10), 1, "insufficient"),
        (next_snapshot(n=400), 1, "traffic exceeds"),
        (replace(next_snapshot(), treatment=Counts(1, 0, 0)), 1, "reset"),
    ],
)
def test_fail_closed(snapshot, now, reason):
    controller = Controller(Config())
    controller.admit(base(), 0)
    assert controller.tick(snapshot, now) == 0
    assert controller.state == State.STOPPING
    assert reason in controller.reason


def test_duplicate_is_not_counted_twice():
    controller = Controller(Config())
    controller.admit(base(), 0)
    snapshot = next_snapshot(1, 1)
    controller.tick(snapshot, 1)
    consumed = controller.ledgers["availability"].enforced
    controller.tick(snapshot, 1)
    assert controller.ledgers["availability"].enforced == consumed


def test_admission_requires_fitting_reserve_and_healthy_baseline():
    with pytest.raises(Unsafe):
        Controller(replace(Config(), reserve_seconds=1)).admit(base(), 0)
    with pytest.raises(Unsafe):
        Controller(Config()).admit(replace(base(), treatment=Counts(1000, 20, 20)), 0)


@pytest.mark.parametrize("policy", ["static", "threshold", "open-loop", "closed-loop"])
def test_every_policy_has_allocation_guard(policy):
    controller = Controller(replace(Config(), policy=policy, severe_burn=200))
    controller.admit(base(), 0)
    controller.tick(next_snapshot(80, 80), 1)
    assert controller.state == State.STOPPING
    assert "allocation safety guard" in controller.reason


def test_total_health_guard_independent_of_attribution():
    controller = Controller(replace(Config(), severe_burn=2))
    controller.admit(base(), 0)
    snapshot = Snapshot(1, "epoch", Counts(1200, 10, 10), Counts(1200, 10, 10))
    controller.tick(snapshot, 1)
    assert controller.ledgers["availability"].signed == 0
    assert "severe total burn" in controller.reason


def test_cleanup_retries_and_reports_failure():
    class Broken:
        def clear(self):
            raise OSError("API unavailable")

        def active(self):
            return True

    controller = Controller(Config())
    assert not controller.cleanup(Broken())
    assert controller.state == State.FAILED


def test_cleanup_requires_readback():
    class Lying:
        def clear(self):
            pass

        def active(self):
            return True

    assert not Controller(Config()).cleanup(Lying())


def test_lock_and_persisted_boundary(tmp_path):
    controller = Controller(Config())
    controller.admit(base(), 0)
    controller.tick(next_snapshot(1, 1), 1)
    checkpoint(tmp_path / "state.json", controller)
    import json

    saved = json.loads((tmp_path / "state.json").read_text())
    assert saved["last"]["timestamp"] == 1
    assert saved["ledgers"]["availability"]["signed"] == 1
    with RunLock(tmp_path / "lock"), pytest.raises(RuntimeError), RunLock(tmp_path / "lock"):
        pass


def test_cooldown_and_burn_window_counts():
    controller = Controller(Config())
    initial = controller.admit(base(), 0)
    controller.tick(next_snapshot(), 1)
    assert controller.intensity == initial  # no actuation inside cooldown
    controller.tick(next_snapshot(timestamp=2, n=400), 2)
    assert controller.intensity < initial  # conservative projected consumption reduces intensity
    controller.tick(next_snapshot(timestamp=3, n=600), 3)
    assert controller.window_burn(2) == {"availability": 0, "latency": 0}
    assert len(controller.history) == 3


def test_burn_window_excludes_boundary_interval():
    controller = Controller(Config())
    controller.history = [
        {"timestamp": 1, "treatment": Counts(100, 1, 1)},
        {"timestamp": 2, "treatment": Counts(100, 0, 0)},
        {"timestamp": 3, "treatment": Counts(100, 0, 0)},
    ]
    assert controller.window_burn(2)["availability"] == 0
    assert controller.window_burn(3)["availability"] == pytest.approx(1 / 300 / 0.01)


def test_cleanup_failure_attempts_are_preserved():
    class Unreachable:
        def clear(self):
            raise OSError("connection lost")

    controller = Controller(Config())
    assert not controller.cleanup(Unreachable(), attempts=3)
    assert len(controller.cleanup_errors) == 3
    assert all("connection lost" in error for error in controller.cleanup_errors)


def test_stop_still_accounts_cleanup_tail_without_restarting_faults():
    controller = Controller(Config())
    controller.admit(base(), 0)
    controller.tick(next_snapshot(2, 2), 1)
    controller.stop("manual stop")
    controller.account_tail(next_snapshot(3, 5, timestamp=2, n=220), 2)
    assert controller.ledgers["availability"].total_bad == 3
    assert controller.ledgers["latency"].total_bad == 5
    assert controller.ledgers["availability"].treatment_requests == 220
    assert controller.state == State.STOPPING and controller.intensity == 0
    with pytest.raises(Unsafe):
        controller.account_tail(next_snapshot(3, 5, timestamp=2, n=220), 2)
