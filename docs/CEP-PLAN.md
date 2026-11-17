# Complete CEP delivery plan

Status: **9 November: 110 selected cluster runs complete; final findings and deliverables prepared.**
Deadline: **16 November 2026**, supplied by the user; the brief and rubric arrived on 15 November (docs/RUBRIC-MATRIX.md). The eight-week
schedule below is historical planning, superseded by the 13-day schedule in IMPLEMENTATION.md.
See IMPLEMENTATION.md for completed checks and corrections, and FULL-STUDY-RUNBOOK.md for the user-selected full-duration study. The measured scope and remaining limitations are in FINAL-RESULTS.md. Student review and viva rehearsal remain before submission.
Simulation checks and short cluster pilots are not final comparative evaluation.
Scope: a reproducible course demonstrator plus an evidence-backed two-column report.
Schedule: provisional eight weeks for two students; adapt to the actual deadline and rubric.

## 1. Success criteria and scope
Build a controller that adjusts fault intensity using remaining availability and latency error budgets. Estimate experiment-attributed consumption from matched control traffic, protect total service health independently, and compare against static and budget-based policies.
Deliver source, pinned deployment manifests, experiment definitions, raw run evidence, reproducible analysis, final paper, slides, and a scripted demonstration.
Do not promise an absolute budget bound: delayed telemetry and fault removal create unavoidable overshoot; quantify it.
Treat the Budget Oracle as an empirical sensitivity summary, not a predictor with an untested guarantee.
MVP: one small application, one faulted dependency, HTTP delay and abort, four policies, two SLOs.
Extension: Online Boutique, Chaos Mesh pod/network faults, additional workloads and uncertainty-aware control.
No production experiments, reinforcement learning, multi-cloud infrastructure, or general causal inference platform in the MVP.

## 2. Requirements and research questions
First obtain the course brief, map each rubric item to an artifact and acceptance check, confirm resources/deadline, and agree the scope with the instructor.
RQ1: Does closed-loop control reduce allocation overshoot compared with static injection, threshold abort, and an open-loop budget-rate schedule?
RQ2: Does attribution improve consumption estimates under known background errors, and where does control contamination invalidate it?
RQ3: What tradeoff exists between safety and useful fault exposure?
RQ4: How do telemetry lag, changing load, and multiple SLO constraints affect controller behavior?
Pre-register primary outcomes and parameter tuning before comparative runs.

## 3. Architecture and stack
Use Kubernetes (kind on Docker/WSL2 if resources allow), Python controller and analysis tools, Prometheus, Grafana, k6, and an instrumented HTTP frontend/dependency application.
Use Istio request matching for treatment-only HTTP delay/abort; use Chaos Mesh separately for scoped pod/network extensions. Never let both inject the same fault path concurrently.
Prove dependency compatibility and record exact versions, image digests, chart values, node resources, and runtime settings before pinning.
Keep the load generator outside the fault boundary. Record ingress request outcomes including client timeouts so mesh-observed successes cannot hide end-user failures.
Use bounded cohort labels, never request IDs as Prometheus labels. A separate trace/log stream can hold per-request identifiers.
Component flow: load -> matched control/treatment stacks -> ingress metrics -> accountant/attribution -> controller -> fault adapter. An independent watchdog removes faults.
The oracle reads completed run evidence and reports budget cost per unit exposure with uncertainty.

## 4. Define SLOs and arithmetic before implementation
Choose a business request endpoint or fixed workload mix. Define eligibility, HTTP failure classes, timeouts, retries, and exclusions once.
Provisional lab targets: availability 99%, latency 95% within 500 ms; calibrate once on a healthy baseline and freeze before comparison. Production-like 99.9% is an optional sensitivity study requiring enough requests.
Availability bad event: failed eligible end-user request. Latency bad event: eligible request exceeding the threshold or timing out, including failures under the chosen conservative definition.
For SLO j, allowed bad fraction q_j = 1 - target_j.
Observed-window budget is q_j * eligible_requests minus bad_requests; burn rate is (bad_requests / eligible_requests) / q_j.
Do not compute budgets from p99 values or subtract a rate directly from a request count.
Maintain separate ledgers per SLO; a request may be bad for both but budgets must not be summed.
Use a fixed experiment accounting horizon and predeclared expected request count to reserve an allocation in bad-request units. For a pilot at 100 requests/s for 10 minutes, 60,000 eligible requests allow 600 availability bad requests at 99%; a 10% allocation is 60 requests.
Freeze the reservation at experiment admission. Account actual events throughout; changing traffic must not manufacture new allocation mid-run. If modeling rolling service budgets, implement a separate timestamped ledger and explicitly track expiry.
Report the laboratory accounting horizon; never equate a short run with validation over a real 30-day SLO window.
Admission requires healthy baseline, positive service budget, sufficient traffic, fresh telemetry, no active conflicting fault, and an allocation no larger than the remaining service budget.
Protect total observed service health independently of estimated attribution.

## 5. Attribution and isolation spike
Randomly assign comparable request mixes to equal-resource stacks. Propagate cohort identity and verify routing, metric labels, and targeted fault application.
Do not assume a header reaches downstream services; demonstrate propagation or target a gateway boundary that preserves assignment.
Avoid shared databases, caches, queues, and noisy-neighbor resources where possible; document residual shared-node interference.
For interval k estimate excess treatment bad requests as treatment_count * (treatment_bad_fraction - control_bad_fraction), using aligned windows and a predeclared baseline correction if needed.
Keep signed estimates for analysis. Use a conservative nonnegative upper estimate for budget enforcement; report clipping bias, confidence, and uncertainty separately.
No causal attribution claim if traffic differs, control is contaminated, or sample counts are inadequate. Fail closed and record the invalid interval.
Validate with synthetic known background failures and treatment-only faults; include a deliberately contaminated control as a negative test.
For pod/network faults, inject only into treatment pods and revalidate isolation; otherwise classify attribution as exploratory.

## 6. Controller and safety design
State machine: IDLE -> PREFLIGHT -> WARMUP -> RUNNING -> STOPPING -> RECOVERY -> COMPLETE; failures go through STOPPING and can end FAILED.
Initial candidate: additive increase, multiplicative decrease with hysteresis, minimum sample counts, cooldown, maximum intensity, and bounded change per tick. Tune on separate pilots.
Start with one actuator dimension: faulted-request percentage, fixed delay magnitude. Abort percentage is a separate fault family.
Each tick uses timestamp-aligned fresh counters, checks all SLOs, and computes remaining allocation minus a lag/cleanup reserve.
Estimate a reserve from measured traffic, worst-case bad fraction, and maximum observation/actuation/removal delay. If no useful reserve fits, refuse admission or stop.
Reduce intensity when projected consumption or short/long burn thresholds threaten any budget; increase only when every constraint and confidence gate allows it.
Stop at duration, consumed allocation/reserve boundary, severe total burn, missing/stale telemetry, insufficient requests, API failure, or manual kill.
Persist run identity, ledgers, last observation boundary, and stop status; avoid double counting after restart and handle counter resets explicitly.
Use least-privilege namespace RBAC, a single active-controller lease, finite fault expiry, and a watchdog with authority to restore known-safe routing.
Istio rules need external expiry/cleanup; do not assume native TTL. Chaos Mesh scenarios need explicit finite duration.
On cleanup failure retry with bounds, mark the run failed, surface a visible alert, and verify fault absence. A stop request alone is not cleanup evidence.
Measure cleanup latency and recovery time; validate watchdog behavior after controller termination.

## 7. Implementation sequence and gates
1. Requirements: rubric matrix, resource inventory, frozen MVP, risk register.
   Gate: feasible deployment choice and no unresolved assessment-critical requirement.
2. Baseline deployment: small app, load, metrics, dashboard, health checks, repeatable teardown.
   Gate: stable latency/error baseline; ingress and client counts reconciled.
3. Accountant: availability/latency ledgers, budget reservation, burn windows, replay fixtures.
   Gate: hand-computed examples and counter-reset/window-boundary tests pass.
4. Fault adapters: treatment-only Istio delay/abort, readback, idempotent restoration, watchdog.
   Gate: finite-duration fault, manual stop, controller-kill cleanup demonstrated.
5. Attribution: aligned cohorts, synthetic background errors, isolation tests.
   Gate: known induced consumption recovered within declared statistical uncertainty.
6. Controller: state machine, safety reserves, all SLO constraints, audit log, replay/dry run.
   Gate: missing data/API/restart scenarios stop safely without duplicate injection.
7. Evaluation runner and oracle: four policy implementations, seeds, random order, complete run metadata.
   Gate: one end-to-end run from deployment through analysis can be repeated.
8. Comparative evaluation, uncertainty analysis, final report and demonstration.
   Gate: every reported result links to raw evidence and exact configuration.

## 8. Evaluation protocol
Policies: fixed intensity; fixed intensity with SLO/budget threshold abort; precomputed open-loop intensity schedule using pilot-estimated budget cost; closed-loop budget controller (total-loss enforcement by default; conditional attribution evaluated separately).
Give every policy identical workloads, initial allocation, intensity bounds, fault duration limit, and emergency safety guard. Report safety-guard interventions separately.
Tune all policies only on pilot seeds and freeze configurations before final experiments.
Core matrix: 4 policies x 2 fault families x 2 loads x 5 seeds = 80 measured runs.
Include 5 no-fault runs per load (10 more). Add an attribution ablation with matched settings and a background-error scenario after the core; keep extension counts explicit.
Calibrate sustainable load first, then use roughly 30% and 70% of measured capacity. Verify neither healthy load violates SLOs.
Suggested run phases: 2-minute warmup, 5-minute fault window, at least 2-minute recovery. Extend until minimum samples and steady-state criteria hold.
At nine minutes per core run, 90 runs require at least 13.5 hours before reset/provisioning; reserve execution time accordingly.
Randomize policy order within matched seed blocks, reset state between runs, and record cluster drift. Repeat noisy/invalid trials under predeclared rules and keep originals.
Measure per-SLO attributed consumption, total bad requests, absolute/relative overshoot, integrated fault exposure, maximum intensity, stop/cleanup/recovery latency, controller overhead, and attribution error.
Define exposure as the time integral of injected percentage for fixed delay; report delay magnitude separately. Define weakness discovery as a reproducible fault/load condition causing a prespecified SLO deviation.
Use paired policy differences across matched seeds, effect sizes, and confidence intervals (bootstrap across independent runs, not individual autocorrelated requests). Five seeds are a starting point, not a significance guarantee.
Report distributions and failed/aborted runs; distinguish insufficient evidence from no effect.
Delivered ablations: attributed vs total burn with known synthetic organic failures; no-fault controls. Single-vs-dual-SLO and deliberately delayed-telemetry cluster ablations were not collected. Independent-ledger and missing-data tests cover implementation behavior only; the unmeasured effects remain explicit limitations, not claimed empirical results.
Plot consumption/allocation over time, intensity and burn rate, overshoot vs exposure, and attribution error. Do not select only favorable traces.

## 9. Verification and evidence
Unit checks: arithmetic/units, zero requests, invalid target, counter resets, rolling boundaries, stale timestamps, separate SLO constraints, reserve calculation.
Replay checks: known faults/background errors, oscillating load, telemetry lag, controller restart, allocation exhaustion.
Integration checks: routing isolation, fault readback/removal, least-privilege RBAC, watchdog on controller death, API failure and cleanup failure.
Each run stores run ID, UTC timestamps, commit/config hashes, pinned versions, seed, workload, SLO targets, allocation, initial conditions, metrics snapshots, controller actions, fault objects, cleanup proof, and exit reason.
Store raw outputs under ignored results/raw/ and preserve/share them as a versioned evidence archive; commit a compact manifest, checksums, and curated tables/plots. Agree retention and archive location before collecting final data.
Analysis must regenerate tables/figures from a named evidence archive using one documented command.

## 10. Report and literature work
Preserve existing Introduction/Literature Review during initialization. Audit every DOI, metadata record, research comparison, novelty assertion, WoS/JCR claim, and claimed search procedure before submission.
The current comparison table marks planned empirical evaluation as supported; revise wording to proposed/planned until measured.
Maintain a literature evidence ledger with primary publisher/DOI link, verification date, supported claim, and limitations. Never treat abstracts as proof of all implementation capabilities.
Finish: abstract after results; problem/formal SLO model; architecture and algorithm; implementation; reproducible experimental setup; results per RQ; threats; conclusion/future work.
Threats: cohort interference, baseline drift, sparse rare failures, percentile estimation, label loss, retries/timeouts, short lab windows, tuning bias, shared-node resources, limited benchmarks.
Use the two-column template, consistent labels/units, readable wide figures/tables, resolved citations, and explicit boundaries between proposed and demonstrated contributions.
Final artifacts: PDF/source, rubric matrix, source/deployment instructions, evidence archive, analysis outputs, slides, and demo recording.

## 11. Schedule and ownership
Week 1: both students map rubric/resources; Khan leads SLO model/accountant, Khalid leads environment/metrics.
Week 2: Khan implements ledgers/tests; Khalid implements load/fault adapter/watchdog; jointly prove isolation.
Week 3: attribution spike, calibrated workload, admission criteria and rollback checks.
Week 4: controller and safety/restart tests; integrate MVP; update methodology draft.
Week 5: baselines, runner, pilot tuning, frozen evaluation protocol and oracle summary.
Week 6: randomized final runs, evidence audit, targeted reruns under declared rules.
Week 7: analysis, plots, results, limitations, citation audit; Online Boutique only if core gates pass.
Week 8: fresh-environment reproduction, final PDF review, slides and rehearsal.
Both review the other's components and can explain the complete system in the viva.
Four-week fallback: small app only, Istio faults only, 3 seeds (48 core runs plus controls), defer Online Boutique/Chaos Mesh extensions, preserve all safety and reproducibility requirements.

## 12. Risks and completion criteria
Insufficient RAM: start without Online Boutique; measure stack footprint before promising the full mesh stack. Use cloud only after agreeing resources and cost ceiling.
Sparse error budgets: increase eligible traffic/run duration or use documented lab targets; do not loosen targets after seeing comparative outcomes.
Actuation/telemetry lag: shorten supported control cadence only after measurement; retain reserve and quantify overshoot.
Contaminated attribution: isolate stacks, run negative controls, and downgrade claims if interference persists.
No verified novelty: present a course engineering contribution and measured comparison without claiming first-ever research.
Definition of done: clean two-column PDF; rubric coverage; repeatable deploy/run/cleanup/analysis; tested safety paths; all final claims traceable to evidence; known limitations stated; rehearsed demo with a prerecorded backup.

## Primary implementation references
These guide engineering; they are not substitutes for verified academic citations.
- Google SRE, Alerting on SLOs: https://sre.google/workbook/alerting-on-slos/
- Istio fault injection: https://istio.io/latest/docs/tasks/traffic-management/fault-injection/
- Istio traffic management (including fault/retry/timeout constraints): https://istio.io/latest/docs/concepts/traffic-management/
- Chaos Mesh HTTP faults: https://chaos-mesh.org/docs/simulate-http-chaos-on-kubernetes/
Recheck documentation against the pinned versions during the compatibility spike.
