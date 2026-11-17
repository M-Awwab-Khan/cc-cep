# Decisions and assumptions

## Accepted initialization choices
- Preserve the existing manuscript filename to minimize Overleaf main-document disruption.
- Keep the two-column CAS class, original vendor sources, and email icon.
- Use bundled cas-model2-names.bst instead of the absent elsarticle-num-names.bst.
- Initialize Git without making an initial commit or configuring a remote.
- Preserve existing research text and bibliography; indexing, novelty, and verification assertions still require evidence.
- Remove unused template distribution examples and documentation; retain original README and manifest.

## Provisional implementation decisions
- Python controller, Prometheus/Grafana observability, Kubernetes, and k6 load generation.
- Start with a small instrumented microservice application; use Online Boutique for external validity after the core works.
- Request-level Istio delay/abort injection for controllable intensity; Chaos Mesh for later infrastructure fault scenarios.
- Prefer independent, matched experiment/control application stacks for attribution; prove isolation and request labeling in a spike.
- Aim for an eight-week schedule with a four-week minimum-scope fallback.

## Historical initialization inputs (superseded by the implementation decisions below)
Course brief/rubric and required CEP learning outcomes; submission date/page limit; laptop CPU/RAM and Docker/WSL availability; cloud credits/provider and cost ceiling; instructor expectations for novelty, experiments, and permitted references.
At initialization, no deployment or cloud spend had been initiated.


## Implementation decisions — 3 November 2026

- User authorized implementation and installation, supplied a 16 November deadline,
  reported no rubric, and freed RAM for a local cluster. Use the neighboring cc-cep Git
  repository; leave the Terraform lab untouched. No cloud spend.
- Install checksum-verified kind 0.33.0, kubectl 1.36.0, Istioctl 1.31.3, Helm 4.3.1,
  k6 2.3.0 under ignored .tools/bin. Pin package resolution in uv.lock. Use digest-pinned
  Python, kind node, Prometheus and Grafana images. Record actual runtime image IDs.
- Dedicated kind cluster cc-cep, namespace cc-cep, separate control/treatment frontend
  and dependency services. Faults target only the treatment dependency hostname; do not
  depend on downstream propagation of a cohort header. Shared-node interference remains.
- Treat client k6 outcome points as count telemetry, including failed connections and
  timeouts. Server Prometheus histograms support inspection, not latency-budget arithmetic.
- Reserve fixed bad-request allocations. Refuse admission when the declared lag/removal
  reserve cannot fit. Pilot's larger laboratory reservation is explicit in PROTOCOL.md;
  it is not evidence over a real long SLO window.
- Keep signed excess estimates and a clipped Wilson-based enforcement screen separately.
  The screen is not a time-uniform confidence guarantee and creates stopping bias.
- Use monotonic time for durations/exposure and UTC timestamps for evidence. Exposure is
  the API-acknowledged command integral; Envoy propagation introduces measurement error.
- Controller restart never resumes an old fault intensity. Use a target lock, atomic
  checkpoints, cleanup-before-admission, finite leases, and a separate bounded watchdog.
  The lock is host-local; a distributed Kubernetes leader lease remains a future gate.
- First cluster spike exposed a shared-resource optimistic-write race. Keep failed/invalid
  evidence. Move watchdog heartbeat to the safety ConfigMap; it no longer rewrites fault
  routing on each heartbeat. Strengthen expiry checks to reject premature removal.
- Include post-stop client counts in cleanup-tail accounting. Checkpoint state and
  preserve cleanup errors rather than treating a stop command as removal proof.
- Preserve all manuscript text and vendor assets. DOI metadata audit is separate from
  claim verification. No final novelty, statistical advantage, or causal claim yet.


## Review-driven corrections and evaluation — 3 November 2026

- Treat the review as a correction list, not confirmation that the CEP is complete.
- Replace accumulated interval-Wilson charges with realized cumulative debit. Default
  enforcement charges observed treatment bad events; background credit requires the
  declared iid/monotonicity assumptions and sequential lower-bound calculation.
- Preserve cleanup failure as sticky even after recovery. Retain every failed attempt.
- Include the original raw archive and checksum in results/evidence. New evidence has
  source snapshots, baseline snapshots, raw organic labels, pod identity/image inventory,
  full ledger replay and client-count reconciliation.
- User explicitly chose the full experiment durations and confirmed machine availability.
  Freeze 80 core runs, 10 controls and 20 subsequent background/debit-mode ablations;
  120/300/120-second phases, randomized blocks 1001–1005, order seed 20261103.
- Capacity-path calibration selected 48 and 112 RPS from a 160 RPS healthy tested level.
  Preserve the failed rollout probe and failed 320 RPS probe. They are not favorable
  data selections hidden from the archive.
- Use pilot seed 21 and independently measured abort/delay costs before freezing. The
  open-loop percentage divides usable budget by fault-window traffic, not reservation traffic.
- Freeze source in a separate local snapshot and detach the one-off sequential process
  from the interactive command session. Runtime links to kubeconfig/tools are excluded
  from archives. A target lock prevents concurrent fault controllers.
- Use paired block bootstrap intervals and preserve missing/failed blocks explicitly.
  Predeclare full-allocation and usable-guard overshoot separately; never represent
  a large reserve as demonstrated tight control of the full allocation.
- Paper revisions now remove the unverified WOS search/gap claim and prototype promises
  about Online Boutique/Chaos Mesh. Those remain optional future extensions.
- Add native Windows lock support and a pinned-actions CI matrix. No Windows execution
  result is claimed; cluster tooling/supervision still uses Linux/WSL.
- Automatic post-study artifacts remain review-required. Do not label data collection,
  report compilation, or plausible novelty as completion of the entire CEP.

### Native-sidecar admission correction (2026-11-03)

The initial full-study-v2 driver was stopped after readiness admission repeatedly
failed before baseline/load generation: Istio 1.31 uses a native sidecar under
initContainerStatuses, while the new provenance check inspected only regular
containerStatuses. All failed attempts and the stopped status are retained. No
measurement-window outcomes were collected. The corrected inventory includes the
named istio-proxy from either location, excluding the completed istio-init. A
regression test checks both layouts. The queue now halts after any trial exhausts
its single invalid-execution retry, so systematic failures cannot consume the
whole plan. Full-study-v3 freezes the correction; its loads, order, seeds, budgets,
phase durations and statistical design are identical to v2. No frozen v2 code was
changed, and no failed trial was relabelled successful.

### Explicit recovery amendment after v3's invalid high-load trial

The v3 study retains two completed comparisons and two invalid attempts of the third
job (core-delay-112-threshold-1001). Missing client iterations invalidate the workload;
health probe timeouts and frontend restarts were also observed. The underlying transient
cause remains unresolved: neither logs nor passing subsequent diagnostics prove a fix.
Independent full-length no-fault (seed 9001) and fault-on (seed 9002) diagnostics at
112 requests/s per cohort completed; both must pass manifest verification and ledger/raw
replay before continuation. They are qualification evidence, not extra comparison runs.

Recovery creates a separate full-study-v4 directory and source freeze. It copies every
prior attempt and carries forward the two valid trials without repeating them. It permits
exactly one additional attempt of the invalid exhausted job, and records this as an
explicit post-failure amendment to the original one-retry rule. A valid unfavorable
result cannot be retried through this path. Other jobs retain the original retry limit.
The measurement/controller/workload/deployment files must match v3 byte-for-byte;
loads, budgets, phases, randomized order and planned analysis are unchanged. A recurrent
invalid trial still halts the batch for diagnosis. No failed outcome is relabelled.

Read-only host memory/load, kind-node resource use, and benchmark container state are
recorded every 30 seconds for diagnosis. Progress distinguishes completed from attempted
jobs. Portable metadata bundles now include resource logs, isolation safety evidence,
prior source/plan/matrix/status, diagnostics and the recovery amendment. The final report
must disclose the amendment and the first-trial concurrent artifact activity; these are
limitations even if the remaining collection succeeds.

The first v4 launch found the project kind node stopped: Docker reported exit 137,
OOMKilled=false, finished at 2026-11-03 15:27:05 UTC. No trial was admitted in that
launch. Only the project-owned node was restarted; all four benchmark pods recovered
to 2/2 Ready. The resumed driver is wrapped by systemd-inhibit (idle:sleep, block),
which releases automatically on process exit and cannot prevent an explicit Docker
shutdown. The failed launch status/log and restart record remain in recovery-evidence.

### Sustained-load replacement after the recovery also failed

The amended v4 retry reproduced frontend health failures during warmup with no fault.
It was stopped with verified cleanup and retained as a failed interrupted attempt.
Temporary SIGUSR1 stack tracing in a separate diagnostic showed active Python request
processing and cgroup CPU throttling; the no-fault load again dropped iterations.
The normal deployment commands were restored and both restorations verified. These
observations support treating the prior capacity qualification as inadequate, without
claiming that CPU throttling is the only proven cause.

The v4 continuation is superseded. A fresh v5 comparison may begin only after four
predeclared full-length no-fault qualifications at conservative 32/64 requests/s pass
health, throughput, identity and CPU-headroom gates. All four must pass once; no adaptive
search or retry-until-success is allowed. Two earlier completed comparisons are retained
as prior engineering evidence, not pooled with v5. Each study phase remains 120/300/120
seconds. The independent 48 requests/s cost pilots remain between the proposed loads.
The one-off qualification/study process runs with sleep inhibition and resource context;
a qualification failure or recurrent invalid study execution halts for diagnosis.

### 8 November audit and fresh qualification amendment

The 3 November qualification stopped after one availability-bad control request in
27,117, with zero treatment bad requests and frontend CPU about 0.46 cores. This failed
the predeclared zero-event gate but not either SLO. The old decision and raw data remain
unchanged. Replacement qualification-02 uses fresh seeds 9201–9204 and per-stream 99%
Wilson upper screening limits <=0.5% availability-bad and <=2.5% latency-bad (half the
SLO bad fractions), plus unchanged traffic, identity, cleanup and resource gates. These
are operational screens, not joint/time-uniform or causal coverage guarantees. All four
fresh runs must pass; the old runs are not reclassified as new qualification evidence.

The audit also corrected exception shutdown ordering: fault removal precedes workload
termination and the guardian remains alive through evidence draining. If cleanup cannot
be verified, its bounded independent process remains available; a clearly declared live
watchdog log is excluded from sealing while an immutable failure snapshot is hashed.
Resume likewise verifies removal before stopping orphan guardians. Runtime templates
and resolved app/proxy images are pinned across the study; raw per-trial pod identity
checks remain. Inference cannot count a run with missing effective metadata as verified.
Attempts.csv independently lists every retained attempt, including unselected failures.
NumPy is now a direct locked dependency; the lock update changes no package versions.

A one-off sleep-inhibited qualification-02/full-study-v6 process will run the original
120/300/120-second phases. Code is snapshotted before qualification and guarded against
changes before freezing evaluation. It emits a best-effort local desktop notice on
failure or exit, and preserves every stopped/superseded run. Completion still requires
110 verified comparisons/controls/ablations, interpretation and final artifact review.

### Final decision-clock correction before replacement comparisons

Qualification-02's first full run passed ledger replay, cleanup and SLO/resource screens.
The second was explicitly interrupted before any comparison began so the final live
freshness correction could be qualified on a consistent source version. Old outcomes
and the interruption remain unchanged. Qualification-03 uses fresh seeds 9301–9304;
full-study-v7 is the sole proposed replacement, with no older trial pooled.

Live observation time was previously also supplied as decision time, hiding API-read
latency in freshness checks. Decisions now use the actual post-inspection clock and
reject stale/future timestamps from either client cohort or the guardian. The adapter
rechecks client telemetry expiry after its own inspection, immediately before fault
writes. New events retain observation/decision times, client latest times and guardian
heartbeat; replay checks these gates for the new clock contract. Manual emergency
interruption is failed/censored, not a completed comparison. These changes improve the
software gate; API outages and Envoy propagation still preclude unconditional safety.

### 9 November: completed measurements and final interpretation

The replacement matrix completed all110 selected runs (80core,10controls,20background).
There are111 retained attempts: host sleep interrupted open-loop abort32/block1003,
its original invalid-execution retry completed, and both verified cleanup. No valid
unfavorable outcome was retried. All96 core paired metric contrasts are complete.

Final interpretation is mixed: guard overshoot improves versus static, while calibrated
open-loop retains substantially more abort exposure. Background point estimates improve
against synthetic tagged residuals without a clear exposure benefit from conservative
credit. No controller tuning or matrix amendment followed these outcomes.

The final paper/deck/demo derive from frozen data and keep the close prior art, shared
host, sequential-block precision, conditional background model and unmeasured cluster
ablations explicit. Single-SLO and injected-telemetry-delay cluster ablations were not
collected and are not presented as completed experiments. A separate independent
portable extraction/replay check and final document QA accompany handoff. Students
still need to review authorship and rehearse; no rubric or remote submission is implied.

## Interactive learning visualizer

- Added a separate static website under visualizer/ using the Sites plugin. It has its own Sites source repository and hosting identity; it does not modify the CEP controller or deploy cluster resources.
- The browser simulation uses seeded synthetic requests, a fixed 120-second reservation, and up to 60 simulated seconds. Default point-estimate accounting and simplified feedback are teaching choices, not proposed fixes or verified research results.
- An optional Wilson-screen mode reproduces the prototype's per-interval formula to explain zero-error enforcement spending. No causal, safety, or superiority guarantee is implied.
- Includes a live sandbox, independent SLO ledgers, four-policy comparison, glossary, guided explanations, quiz, accessible chart data, and JSON export.
- Verified nine model checks plus Chrome interactions and desktop/mobile layout. Publication defaults to owner-private.

## 15 November follow-up: budget-paced closed loop (post-result, separate evaluation)

- Review of v7 traces showed the original closed-loop policy was limited by SRE burn-rate
  gates (interval bad fraction / q: halve above 2, increase only below 1), not by its
  budget. With q = 1%, abort intensity oscillated between 0.5% and about 2.3% and spent
  about 30% of the usable allocation (block 1001, 32 requests/s: 148 of 480); delay
  intensity stayed at the 5% latency burn = 1 boundary.
- Added policy `paced` in `core.py`. Its gates measure consumption relative to the rate
  that spends the remaining usable allocation (A - D - R) over the remaining fault window.
  It halves if cumulative projected risk > 1 or short pace > 2 with long pace > 1, and
  increases by the unchanged step only if every SLO has risk < 0.9 and short/long pace < 1.
  Allocations, reserve, caps, step, cooldown, windows and all common guards are unchanged.
  The original `closed-loop` policy is unchanged so frozen v7 evidence still replays.
- This change followed v7 outcomes, so it is evaluated as `followup-paced-v1`: 20 runs
  (2 faults x 2 loads x blocks 1001-1005), randomized within blocks with order seed
  20261115, full 120/300/120-second phases. It is compared with v7 runs that share block
  IDs, but the pairing is time-separated and not jointly randomized; it is never pooled
  into the v7 comparison. Runtime anchor (images/templates) matched v7 at preparation.
- Collection ran on the separate Linux workstation over SSH; the idle-sleep inhibitor was
  granted but sleep/lid inhibition was refused by polkit, so the operator must keep it awake.
- Outcome (15 November, collected 10:25-13:45 UTC): 20/20 runs valid, 128/128 planned
  comparisons. Paced spent 98-100% of usable allocation (closed-loop: 29-30% abort,
  93-94% delay). Exposure 14.8-15.4 fraction-seconds, within 0.62 of static (all
  intervals include zero); +10.9 vs closed-loop for aborts, +0.8-1.0 for delays.
  Mean guard overshoot 0.8-1.6 requests (static 4.6-21.6); 9 runs overshot by 1-4
  requests, 7 ended by the allocation safety guard; max total 964 of 2,310 allocation.
  A tailnet outage during run 18 did not affect local collection. Outputs:
  `followup-*.csv`, `followup-summary.json`, `results/curated/followup-table.tex`,
  `results/curated/followup-results.tex` (report Section 6.6, Table 9).
## Visualizer alignment with the final study — 15 November 2026

- The visualizer's repository mode was the retired v1 per-interval Wilson charge. Added a four-way accounting selector; the default remains the teaching point estimate. Repository v2 (cumulative observed treatment debit, high-water mark) and v2 plus iid background credit port the current Python accounting. The v1 mode is retained only as a labelled contrast with the corrected algorithm.
- Background credit is ported from `uncertainty.py` with a Lanczos log-gamma; tests compare outputs with the Python implementation to 1e-6 relative. The lab's synthetic background is iid by construction, so the credit's assumptions hold there and are stated as not guaranteed elsewhere.
- Added a Real study results page generated from `results/curated/final-study-summary.json`; the retained failed attempt, descriptive intervals and limitations are shown. It is deliberately separate from the simulator. Prose findings are paraphrased from `docs/FINAL-RESULTS.md` and flagged for verification against the manuscript.
- Not ported: multiwindow burn history, telemetry freshness, minimum-traffic gate, and watchdog behavior. These remain explained in text and the glossary only.
