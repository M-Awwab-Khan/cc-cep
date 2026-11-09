# Protocol history and current version

**Superseded for new runs:** this file preserves the original pilot design and its
known interval-Wilson defect. The current accountant is described in docs/ACCOUNTING-V2.md.
The user selected the full-duration study in FULL-STUDY.md on 3 November 2026. Its
immutable plan.json, pilot costs and source snapshot are authoritative for evaluation.
Historical simulations/pilots remain evidence of that earlier version, not final cluster data.

# Pilot and evaluation protocol

Deadline: **16 November 2026** (user supplied). No rubric supplied.

The existing plan's Kubernetes study remains the target. Model runs are implementation
checks and pilots, not final comparisons. Seeds 101–105 are development seeds; reserve
1001–1005 for eventual evaluation, and freeze settings before using them. Order seed:
20261103. Do not tune on final seeds.

Current four policies share the same allocation/total-health emergency guard. `static`
uses maximum configured intensity; `threshold` additionally stops on interval burn >=2;
`open-loop` fixes intensity from a supplied pilot cost; `closed-loop` uses projected
conservative consumption and additive-increase/multiplicative-decrease. No claim of
optimality or proven bound. The controller uses whole-interval short/long burn windows, separate risk thresholds
for increasing/decreasing intensity, and a cooldown. These settings need pilot tuning
and must be frozen before final comparison.

SLOs: availability 99%; conservative latency 95% under 500 ms. Failed requests count
against both. Classification comes from the client; server metrics are supporting.
No retries. Connection errors/timeouts count as failures. One request can consume both
ledgers but the ledgers are never added together.

Admission freezes expected treatment request count and allocation. Baseline sampling
precedes the accounting horizon. Total service health and allocation are separate checks.
`max_rps * reserve_seconds` reserves worst-case bad requests during the declared lag and
removal envelope. The envelope must be measured and configured for the actual actuator.
The model default 0.1 seconds is a synthetic assumption, NOT a Kubernetes setting.

**Feasibility gate:** the draft 60-request allocation with 300 requests/s permits less
than 0.2 seconds of worst-case delay. A multi-second mesh cleanup path cannot fit it.
Changing traffic alone does not solve this if reservation and reserve both scale with
traffic. Calibrate lag first, then predeclare a defensible horizon/allocation, or report
that safe admission is infeasible. Do not reduce the reserve to obtain a favorable run.

The per-interval Wilson-based upper estimate is a conservative screening heuristic. It
is not a simultaneous or time-uniform confidence bound. Clipping/summing interval bounds
can exhaust an allocation even without injected errors. Preserve signed estimates and
report stopping/exposure bias. Evaluate this explicitly before selecting the final
controller, possibly replacing the screen with a preregistered sequential method.

Final cluster matrix, if gates pass: four policies × two faults × two calibrated loads ×
five seeds = 80 runs, plus ten no-fault controls. Matched seed blocks, randomized policy
order, identical configs and guards. Loads must come from capacity measurements, not the
arbitrary 150/250 RPS model settings. Add explicit attribution ablation/contamination
experiments after core validation. No-fault controls and ablations have NOT been run as
part of the current 80 model trials.

Preserve all failed/admission-rejected/aborted runs. Primary outcomes: per-SLO signed and
enforced consumption, overshoot, exposure, cleanup and recovery latency. Analyze paired
run differences and run-level confidence intervals; current plot/CSV is descriptive
only. Record config/source hashes, lockfile hash, seed, UTC time, workload, and cleanup
proof. Archive raw evidence with checksums before deletion of ephemeral cluster storage.

The initial live engineering pilot explicitly uses a two-hour *reservation* horizon
at 50 treatment requests/s (360,000 expected requests), availability allocation 50%
and latency allocation 10%, a 15-second reserve at a 100 RPS cap, and a 30-second
fault window. This changes the provisional reservation to admit a multi-second
watchdog path; it does not measure two hours of service or validate a two-hour SLO.
Those generous pilot settings are NOT final experimental settings. A 60-request
reservation would be rejected for this actuator.
