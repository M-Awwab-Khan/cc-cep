"""Count-based, fixed-reservation SLO accounting and fail-closed control."""

import math
from dataclasses import dataclass, field
from enum import StrEnum


class Unsafe(ValueError):
    pass


@dataclass(frozen=True)
class SLO:
    name: str
    target: float
    allocation_fraction: float = 0.1

    def __post_init__(self):
        if not self.name or not 0 < self.target < 1 or not 0 < self.allocation_fraction <= 1:
            raise ValueError("invalid SLO")

    @property
    def q(self):
        return 1 - self.target


@dataclass(frozen=True)
class Counts:
    total: int
    availability: int
    latency: int

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in self.__dict__.values()):
            raise ValueError("counts must be nonnegative integers")
        if max(self.availability, self.latency) > self.total:
            raise ValueError("bad requests cannot exceed eligible requests")
        if self.latency < self.availability:
            raise ValueError("conservative latency SLI must include failures")

    def delta(self, previous):
        values = [getattr(self, k) - getattr(previous, k) for k in self.__dict__]
        if min(values) < 0:
            raise Unsafe("counter reset")
        return Counts(*values)


@dataclass(frozen=True)
class Snapshot:
    timestamp: float
    epoch: str
    control: Counts
    treatment: Counts
    isolation_ok: bool = True


def wilson(bad, total, z=1.96):
    if total <= 0:
        raise Unsafe("no samples")
    p = bad / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0, center - radius), min(1, center + radius)


def attributed(treatment_bad, treatment_n, control_bad, control_n):
    """Signed difference plus conservative marginal-Wilson enforcement estimate.

    This is a per-interval screening bound, NOT a time-uniform budget guarantee.
    Repeated clipping creates bias; retain both estimates in all evidence.
    """
    signed = treatment_bad - treatment_n * control_bad / control_n
    upper = treatment_n * max(
        0, wilson(treatment_bad, treatment_n)[1] - wilson(control_bad, control_n)[0]
    )
    return signed, upper


@dataclass(frozen=True)
class Config:
    slos: tuple[SLO, ...] = (SLO("availability", 0.99), SLO("latency", 0.95))
    expected_treatment_requests: int = 60000
    duration: float = 300
    max_age: float = 5
    min_requests: int = 100
    max_rps: float = 300
    reserve_seconds: float = 0.1
    max_intensity: float = 0.1
    step: float = 0.005
    severe_burn: float = 20
    policy: str = "closed-loop"
    pilot_cost: float = 1.0
    short_window: float = 5
    long_window: float = 30
    cooldown: float = 2

    def __post_init__(self):
        if any(type(v) is not int for v in (self.expected_treatment_requests, self.min_requests)):
            raise ValueError("request counts must be integers")
        positive = (
            self.expected_treatment_requests,
            self.duration,
            self.max_age,
            self.min_requests,
            self.max_rps,
            self.reserve_seconds,
            self.step,
            self.severe_burn,
            self.pilot_cost,
            self.short_window,
            self.long_window,
            self.cooldown,
        )
        if any(not math.isfinite(v) or v <= 0 for v in positive):
            raise ValueError("configuration values must be finite and positive")
        if self.short_window > self.long_window:
            raise ValueError("short burn window exceeds long window")
        if not 0 < self.max_intensity <= 1:
            raise ValueError("invalid intensity")
        if {s.name for s in self.slos} != {"availability", "latency"} or len(self.slos) != 2:
            raise ValueError("exactly availability and latency SLOs required")
        if self.policy not in {"static", "threshold", "open-loop", "closed-loop"}:
            raise ValueError("unknown policy")


class State(StrEnum):
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    WARMUP = "WARMUP"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    RECOVERY = "RECOVERY"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass
class Ledger:
    allocation: float
    service_budget: float
    signed: float = 0
    enforced: float = 0
    total_bad: int = 0
    treatment_requests: int = 0


@dataclass
class Controller:
    config: Config
    state: State = State.IDLE
    intensity: float = 0
    reason: str = ""
    ledgers: dict[str, Ledger] = field(default_factory=dict)
    last: Snapshot | None = None
    failed: bool = False
    started: float = 0
    history: list = field(default_factory=list)
    last_change: float = 0
    cleanup_errors: list[str] = field(default_factory=list)

    @property
    def reserve(self):
        # Worst case: every treatment request during observation/removal is bad.
        return self.config.max_rps * self.config.reserve_seconds

    def stop(self, reason):
        self.intensity = 0
        self.reason = reason
        self.state = State.STOPPING
        return 0.0

    def admit(self, baseline: Snapshot, now: float):
        if self.state != State.IDLE:
            raise Unsafe("run already admitted")
        self.state = State.PREFLIGHT
        try:
            self._fresh(baseline, now)
            self.state = State.WARMUP
            if min(baseline.control.total, baseline.treatment.total) < self.config.min_requests:
                raise Unsafe("insufficient baseline traffic")
            for slo in self.config.slos:
                for cohort in (baseline.control, baseline.treatment):
                    if getattr(cohort, slo.name) / cohort.total > slo.q:
                        raise Unsafe("unhealthy baseline")
                service = slo.q * self.config.expected_treatment_requests
                allocation = service * slo.allocation_fraction
                if allocation <= self.reserve:
                    raise Unsafe("allocation cannot cover lag/removal reserve")
                self.ledgers[slo.name] = Ledger(allocation, service)
            self.last_change = baseline.timestamp
            self.started = baseline.timestamp
            self.last = baseline
            self.state = State.RUNNING
            return self._policy_initial()
        except (ValueError, ArithmeticError):
            self.failed = True
            self.stop("admission rejected")
            raise

    def _policy_initial(self):
        self.intensity = min(self.config.step, self.config.max_intensity)
        if self.config.policy in {"static", "threshold"}:
            self.intensity = self.config.max_intensity
        elif self.config.policy == "open-loop":
            self.intensity = min(
                self.config.max_intensity,
                min(ledger.allocation for ledger in self.ledgers.values())
                / self.config.expected_treatment_requests
                / self.config.pilot_cost,
            )
        return self.intensity

    def _fresh(self, snapshot, now):
        if not math.isfinite(snapshot.timestamp) or not math.isfinite(now):
            raise Unsafe("invalid timestamp")
        if not 0 <= now - snapshot.timestamp <= self.config.max_age:
            raise Unsafe("stale or future telemetry")
        if not snapshot.isolation_ok:
            raise Unsafe("cohort isolation invalid")
        if not snapshot.epoch:
            raise Unsafe("missing counter epoch")

    def tick(self, snapshot: Snapshot, now: float):
        if self.state != State.RUNNING:
            return 0.0
        try:
            self._fresh(snapshot, now)
            if snapshot.epoch != self.last.epoch:
                raise Unsafe("counter epoch changed")
            dt = snapshot.timestamp - self.last.timestamp
            if dt <= 0:
                raise Unsafe("duplicate or out-of-order telemetry")
            if dt > self.config.max_age:
                raise Unsafe("telemetry gap")
            c = snapshot.control.delta(self.last.control)
            t = snapshot.treatment.delta(self.last.treatment)
            if min(c.total, t.total) < self.config.min_requests:
                raise Unsafe("insufficient interval traffic")
            if t.total / dt > self.config.max_rps:
                raise Unsafe("traffic exceeds reserve assumption")
            self.last = snapshot
            burn = {}
            for slo in self.config.slos:
                ledger = self.ledgers[slo.name]
                signed, upper = attributed(
                    getattr(t, slo.name), t.total, getattr(c, slo.name), c.total
                )
                ledger.signed += signed
                ledger.enforced += upper
                ledger.total_bad += getattr(t, slo.name)
                ledger.treatment_requests += t.total
                burn[slo.name] = getattr(t, slo.name) / t.total / slo.q
            self.history.append(
                {
                    "timestamp": snapshot.timestamp,
                    "burn": burn,
                    "intensity": self.intensity,
                    "treatment": t,
                }
            )
            for name, ledger in self.ledgers.items():
                if ledger.total_bad + self.reserve >= ledger.service_budget:
                    return self.stop(f"total service budget: {name}")
                if burn[name] >= self.config.severe_burn:
                    return self.stop(f"severe total burn: {name}")
                # Identical emergency guard for all policies. Report separately from policy stop.
                if ledger.enforced + self.reserve >= ledger.allocation:
                    return self.stop(f"allocation safety guard: {name}")
            if snapshot.timestamp - self.started >= self.config.duration:
                return self.stop("duration")
            if self.config.policy == "threshold" and max(burn.values()) >= 2:
                return self.stop("threshold policy")
            if self.config.policy == "closed-loop" and (
                snapshot.timestamp - self.last_change >= self.config.cooldown
            ):
                short_burn = self.window_burn(self.config.short_window)
                long_burn = self.window_burn(self.config.long_window)
                remaining_time = max(dt, self.config.duration - (snapshot.timestamp - self.started))
                risk = max(
                    (self.ledgers[s.name].enforced / max(dt, snapshot.timestamp - self.started))
                    * remaining_time
                    / max(
                        1e-12,
                        self.ledgers[s.name].allocation
                        - self.ledgers[s.name].enforced
                        - self.reserve,
                    )
                    for s in self.config.slos
                )
                previous_intensity = self.intensity
                if risk > 1 or (max(short_burn.values()) > 2 and max(long_burn.values()) > 2):
                    self.intensity *= 0.5
                elif risk < 0.5 and max(short_burn.values()) < 1 and max(long_burn.values()) < 1:
                    self.intensity = min(
                        self.config.max_intensity, self.intensity + self.config.step
                    )
                if self.intensity != previous_intensity:
                    self.last_change = snapshot.timestamp
            return self.intensity
        except (ValueError, ArithmeticError) as exc:
            self.failed = True
            return self.stop(str(exc))

    def account_tail(self, snapshot: Snapshot, now: float):
        """Drain exact client counts through removal; stopping must not hide cleanup damage."""
        self._fresh(snapshot, now)
        if self.last is None or snapshot.epoch != self.last.epoch:
            raise Unsafe("tail epoch mismatch")
        if snapshot.timestamp <= self.last.timestamp:
            raise Unsafe("tail boundary did not advance")
        c = snapshot.control.delta(self.last.control)
        t = snapshot.treatment.delta(self.last.treatment)
        for slo in self.config.slos:
            ledger = self.ledgers[slo.name]
            bad = getattr(t, slo.name)
            ledger.total_bad += bad
            ledger.treatment_requests += t.total
            if t.total and c.total:
                signed, upper = attributed(bad, t.total, getattr(c, slo.name), c.total)
                ledger.signed += signed
                ledger.enforced += upper
            elif t.total:
                # Attribution unavailable, but all treatment bad events remain charged.
                ledger.enforced += bad
                self.failed = True
                self.reason += "; tail control samples unavailable"
        self.last = snapshot

    def window_burn(self, seconds):
        # Include whole observed intervals ending inside the window. No invented fractional counts.
        end = self.history[-1]["timestamp"]
        samples = [h["treatment"] for h in self.history if h["timestamp"] > end - seconds]
        n = sum(c.total for c in samples)
        return {
            s.name: sum(getattr(c, s.name) for c in samples) / n / s.q for s in self.config.slos
        }

    def cleanup(self, adapter, attempts=3):
        self.state = State.STOPPING
        self.intensity = 0
        for _ in range(attempts):
            try:
                adapter.clear()
                if not adapter.active():
                    self.state = State.RECOVERY
                    return True
                self.cleanup_errors.append("fault remains active after clear")
            except Exception as exc:
                self.cleanup_errors.append(repr(exc))
        self.reason = f"cleanup failed; {self.reason}"
        self.state = State.FAILED
        return False
