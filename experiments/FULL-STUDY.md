> Final code freeze candidate: qualification-03 seeds 9301–9304 / full-study-v7.
> Qualification-02's first run passed but the sequence was interrupted before any
> comparison to qualify the corrected decision-time freshness implementation. The
> Wilson/resource screens and 120/300/120-second phases are unchanged. All prior
> observations remain archived and are excluded from the replacement comparison.

> 8 November final pre-collection amendment: qualification-02 seeds 9201–9204 screen
> each stream using a 99% Wilson upper limit <=0.5% availability-bad / <=2.5% latency-bad,
> with unchanged throughput, CPU, identity and cleanup gates. All four fresh full-length
> runs must pass before full-study-v6; earlier data is not pooled or relabelled. These
> finite-sample operating screens make no joint or causal coverage claim.

> 8 November replacement: qualification-02 uses fresh seeds 9201–9204 and per-stream
> 99% Wilson upper screening limits <=0.5% availability-bad and <=2.5% latency-bad.
> This replaces the overly strict zero-event pilot screen; old failures remain unchanged.
> Four full-length 32/64 requests/s runs must pass before fresh full-study-v6. Throughput,
> CPU, pod identity and cleanup gates remain. The earlier protocol history follows.

> Replacement protocol: v3/v4 high-load execution proved unreliable. The proposed fresh
> v5 comparison uses 32/64 requests/s only after all four predeclared sustained
> qualifications pass. Earlier comparisons are not pooled. See the replacement section
> below; 120/300/120-second phases and the 110-trial design remain unchanged.

# Full-duration study specification, frozen before evaluation

The user explicitly selected the full phase durations on 3 November 2026 and confirmed
that the machine can remain on. Main matrix: 80 cluster comparisons plus 10 controls.
A further 20 background/attribution ablation runs follow the main matrix.

Each run has 120 seconds warmup, a 300-second maximum fault window, at least 120 seconds
recovery and a five-second load-generator completion allowance. A policy stop removes
the fault immediately but keeps no-fault load through the rest of the shared horizon.
The generator finishes naturally; it is not intentionally cancelled mid-request.
Main runtime is at least 13.6 hours; all 110 runs require at least 16.7 hours, plus setup,
safety refreshes, analysis and any invalid-execution retries. Keep Docker and the host
awake. There is no cloud spending.

## Calibration and independent pilots

Revision capacity calibration found healthy no-fault levels at 80 and 160 requests/s
per cohort, then failed at 320 with load-generator drops and high latency. Select 48 and
112 requests/s, 30% and 70% of the highest tested healthy path rate. This measures the
host/kubectl/service path, not universal application capacity. The first invalid probe
attached during a rollout; it remains retained and is not used for selection.

Independent 30-second static cost pilots use seed 21 at 48 requests/s, 10% intensity and
fixed 600 ms delay or HTTP abort. Estimate cost per exposed treatment request from the
maximum signed SLO loss divided by RPS times command exposure. Store the exact measured
cost and pilot checksum in plan.json before evaluation. Do not adjust after viewing
block IDs 1001–1005. Istio RNG is not controlled by those identifiers; they define
randomized replication blocks, not identical realized fault draws.

## Fixed reservation and feasibility

For load r, traffic cap = ceil(1.4r), reserve R = cap * 15 seconds, usable headroom
H = ceil(r * 0.1 * 300 * 0.5), and each SLO allocation A = R + H. The reservation's
expected traffic is ceil(2A/0.01)+1; choose per-SLO allocation fractions so availability
and latency receive equal bad-request allocations while retaining distinct ledgers.
The accounting horizon is explicitly longer than the observed run and is not validated
as a long-window SLO. Report full A overshoot and the safety-adjusted threshold A-R
separately. A large reserve must not be presented as tight empirical control of A.

The current 15-second envelope includes the six-second lease, two-second observation
cadence, two-second client timeout and an API margin. This is an operating assumption,
not a deterministic bound through arbitrary API outages. Record delayed observations,
cleanup failures and overshoot rather than promising a guarantee.

## Policies and outcomes

Static: 10% injection, subject to common emergency guards.
Threshold: same initial injection plus interval-burn >=2 stop.
Open loop: fixed percentage from usable headroom / (fault-window requests * pilot cost).
Closed loop: fixed additive step .005, multiplicative decrease .5, five/30-second whole
interval burn windows, two-second cooldown, declared dual constraints.

Common guards: allocation/reserve boundary, total service health, severe burn >=20,
freshness <=5 seconds, at least 50 eligible outcomes per cohort per observation, declared
traffic cap, watchdog heartbeat and explicit emergency stop. Admission requires a
healthy 120-second baseline. No-fault controls apply no fault and record zero exposure.

Primary outcomes: per-SLO full-allocation overshoot, usable-guard overshoot, total bad
requests, command exposure and cleanup status. Retain signed estimates separately.
Use closed-loop minus comparator differences within each matched replication block.
Percentile bootstrap across five independent blocks uses 10,000 resamples and 95%
descriptive intervals. Do not bootstrap individual requests. No multiplicity adjustment;
limited power and interval precision must be reported. Empirical cost summaries have
no prospective guarantee.

## Background and invalid controls

After core collection, compare attributed and total-debit modes at each load and each
block under a declared 0.5% independent synthetic organic error probability. Request
keys and seeds generate organic responses independently by cohort; the raw outcome point
records its organic label. The non-organic residual is a controlled reference, not
universal fault-causal ground truth. Exact organic labels allow attribution-error
comparisons; code/model assumption limits remain explicit.

An additional small negative gate check declares a noncomparable/contaminated control
and must refuse admission. This is a configured safety check, not automatic discovery
of unknown contamination. Shared-node interference remains a threat.

## Failures, source freeze and recovery

Source and package environment freeze before evaluation. Policy order is randomized
within blocks using seed 20261103 and persisted before collection. Record all attempts.
At most one retry is allowed for failed admission/execution/replay; never repeat a
valid outcome because it is unfavorable. Missing blocks yield incomplete paired
inference rather than silently reducing n. Cleanup that remains unverified halts the
queue before another injection. A later recovery never clears the original failure.

Each trial contains source.tar.gz, effective config, baseline, raw k6 points, observation
snapshots, cleanup/tail counts and checksums. Replay reconstructs every revised ledger
and reconciles raw cohort totals. Immutable per-attempt bundles and a hash-verified
multi-part index support sharing. Old development evidence remains separately versioned.

The completion state ARTIFACTS_BUILT_REVIEW_REQUIRED means data processing/rendering
finished. It does not mean that novelty, the final PDF/slides, or the CEP received final
human/visual review. Delayed-telemetry and single-SLO sensitivity studies, distributed
leadership validation and larger benchmarks remain explicitly outside this core run.

## Sustained qualification and fresh replacement study

The one-off scripts/qualify_and_study.py declares rates [32,64,32,64], independent seeds
9101–9104 and full 120/300/120-second no-fault phases before any replacement comparison.
Every run must complete, verify cleanup, replay raw counts, preserve pod identity/readiness,
retain at least 400 seconds of post-baseline traffic per cohort, report zero availability
failures and at most 1% latency-bad outcomes in each cohort. Average frontend CPU must
remain <=0.70 cores and CPU throttled time <=5% of wall time. A failure halts: there is
no automatic rate search, repeated qualification until success, or relaxed safety gate.

If all four pass, v5 starts a fresh 80 comparisons +10 controls +20 background ablations
at 32/64 requests/s. Prior v3/v4 data stays archived and is not pooled with new results.
Independent 48 requests/s cost pilots remain the calibration reference between the two
new loads. Algorithm, budgets as a function of traffic, policy order, seeds, phase lengths
and statistical methods follow the design above. CPU headroom reduces saturation risk;
it does not establish a universal hardware capacity or exclude every transient failure.
