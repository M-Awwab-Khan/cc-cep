"""Budget-paced policy: gates are relative to the experiment's own planned spend."""

import pytest

from cc_cep.core import SLO, Config, Controller, Counts, Snapshot, State

# Usable allocation 3000 bad requests over 300 s at 200 treatment requests/s means a
# sustainable fault fraction of 5%; SRE burn gates would cap aborts near 2% (q = 1%).
CONFIG = dict(
    slos=(SLO("availability", 0.99, 0.5), SLO("latency", 0.95, 0.1)),
    expected_treatment_requests=606000,
)


def simulate(policy, ticks=290, family="abort", n=200):
    controller = Controller(Config(policy=policy, **CONFIG))
    total = control = 1000
    bad = 0
    controller.admit(Snapshot(0, "e", Counts(control, 0, 0), Counts(total, 0, 0)), 0)
    trace = []
    for t in range(1, ticks + 1):
        increment = round(controller.intensity * n)
        total, control, bad = total + n, control + n, bad + increment
        availability = bad if family == "abort" else 0
        controller.tick(
            Snapshot(t, "e", Counts(control, 0, 0), Counts(total, availability, bad)), t
        )
        trace.append(controller.intensity)
        if controller.state != State.RUNNING:
            break
    return controller, trace


def test_paced_spends_budget_that_burn_gates_leave_unused():
    paced, paced_trace = simulate("paced")
    closed, closed_trace = simulate("closed-loop")
    assert max(closed_trace) <= 0.025  # burn-rate gate: availability burn = intensity / 1%
    assert max(paced_trace) >= 0.045
    assert paced.state == State.RUNNING  # no allocation guard trip inside the window
    usable = paced.ledgers["availability"].allocation - paced.reserve
    assert 0.6 * usable <= paced.ledgers["availability"].enforced < usable
    assert closed.ledgers["availability"].enforced < 0.5 * paced.ledgers["availability"].enforced


def test_paced_delay_is_limited_by_latency_pace_not_idle_availability():
    paced, trace = simulate("paced", family="delay")
    assert paced.ledgers["availability"].enforced == 0
    assert max(trace) >= 0.045
    assert paced.ledgers["latency"].enforced < paced.ledgers["latency"].allocation - paced.reserve


def test_paced_halves_on_sustained_overspend():
    controller = Controller(Config(policy="paced", **CONFIG))
    controller.admit(Snapshot(0, "e", Counts(1000, 0, 0), Counts(1000, 0, 0)), 0)
    controller.tick(Snapshot(1, "e", Counts(1200, 0, 0), Counts(1200, 0, 0)), 1)
    before = controller.intensity
    # About 33 bad/s over the window is over 3x the sustainable ~10 bad/s, while the
    # 16.7% interval bad fraction stays below the common severe-burn emergency guard.
    controller.tick(Snapshot(3, "e", Counts(1800, 0, 0), Counts(1800, 100, 100)), 3)
    assert controller.intensity == pytest.approx(before * 0.5)


def test_pace_is_per_slo_and_window_rate_uses_interval_durations():
    controller = Controller(Config(policy="paced", **CONFIG))
    controller.admit(Snapshot(0, "e", Counts(1000, 0, 0), Counts(1000, 0, 0)), 0)
    controller.tick(Snapshot(2, "e", Counts(1400, 0, 0), Counts(1400, 0, 8)), 2)
    assert controller.window_rate(5) == {"availability": 0, "latency": 4}
    pace = controller.pace(2, 2)
    assert pace["availability"] == (0, 0, 0)
    risk, short, long = pace["latency"]
    usable = controller.ledgers["latency"].allocation - 8 - controller.reserve
    assert short == pytest.approx(4 / (usable / 298))
    assert risk == pytest.approx(4 * 298 / usable)
