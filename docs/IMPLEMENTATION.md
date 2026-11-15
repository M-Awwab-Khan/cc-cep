# Implementation and runbook

Working repository: `/home/muhammad-abyaz/workspace/personal/cc/cc-cep`.
Deadline: **16 November 2026**. No rubric supplied.

## Final measured status — 9 November 2026

The replacement dataset has 110 verified selected runs, 111 retained attempts, 96 complete
core paired metric comparisons and 16 background comparisons. All attempts verified
cleanup. The single failed execution was interrupted by host sleep and retried under
the existing rule. See FINAL-RESULTS.md for findings, artifacts and reproduction.
The Linux suite passes 59 tests. Native Windows CI and distributed leadership remain
unvalidated. Earlier notes below describe historical implementation and pending gates;
ACCOUNTING-V2.md and the final findings supersede their interval-Wilson description.

## Review correction status — 3 November 2026

- Fixed zero-error consumption by separating realized cumulative debit from uncertainty.
  See ACCOUNTING-V2.md; default enforcement cannot exceed observed treatment bad counts.
- Cleanup exhaustion now sets a sticky failed flag; subsequent removal preserves failure.
- Real corrected no-fault control: 2,006 healthy treatment requests, zero consumption,
  duration stop. Baseline/observations/raw client totals replay successfully.
- Original raw development archive is included in results/evidence, not merely referenced
  by an absent ignored path. A portable verifier checked 169 manifests successfully.
- Revised trials include per-run source snapshots, explicit baselines, raw cohort/organic
  outcomes, pod identities/image IDs, cleanup tail, and checksums. Source freezes for the
  unattended full study. All invalid attempts remain retained.
- Added paired block-bootstrap analysis and background-debit ablation analysis. These are
  implemented methods; final numeric comparisons require completed cluster collection.
- The paper now has substantive abstract/methodology/implementation/results-status/
  threats/conclusion sections. Removed unverified search/gap claims and unimplemented
  benchmark promises. The compiled PDF and eight-slide deck are interim, not final study findings.
- Native Windows collection no longer imports fcntl unconditionally; dependencies remain
  mandatory. Windows CI is configured but has not run here. Cluster execution uses Linux/WSL.
- The user chose full 120/300/120-second phases. See FULL-STUDY-RUNBOOK.md for the sequential,
  resumable 80 core +10 controls +20 background runs. Do not claim CEP completion while
  collection or final artifact review remains pending.

Historical implementation notes below describe the first prototype. Where they mention
interval Wilson screening, ACCOUNTING-V2.md supersedes that algorithm.

## Implemented

- Fixed, independent availability and conservative latency request-count ledgers;
  signed matched-cohort attribution and a separate Wilson-based enforcement estimate.
- Healthy admission, finite duration, lag/removal reserve, traffic/freshness/isolation
  gates, counter reset/epoch protection, total-health guard, allocation guard.
- Static, threshold-stop, open-loop, and closed-loop policies; short/long burn windows,
  cooldown and separate increase/decrease thresholds. These are candidate algorithms.
- Atomic checkpoints, host-local target lock, cleanup-before-admission on restart,
  cleanup retries/readback and error recording, post-stop accounting tail.
- Separate benchmark stacks, client outcomes including timeouts, server Prometheus
  metrics, treatment-dependency Istio delay/abort, finite external fault leases.
- Independent watchdog, emergency-stop file, raw k6 points, run metadata/source hashes,
  checksums, seeded model matrix, CSV/plot generation and descriptive empirical costs.
- Digest-pinned local Kubernetes/benchmark/observability deployment and checksum-verified
  CLI installer. `uv.lock` pins the Python environment; no global packages or cloud spend.

## Verified on this machine

See `results/curated/` and the raw archive manifest for actual evidence. Checks include
hand-computed arithmetic, independent SLOs, malformed counts/targets, missing/stale data,
reset/epoch/repeated boundaries, safety guards for all policies, cleanup failures,
atomic checkpoints/exclusive locking, whole-interval burn windows, cooldown, client
point parsing, tamper detection, and contamination rejection.

Real loopback checks covered abort/delay isolation, healthy recovery and lease expiry
when the renewer was killed. The real kind/Istio spike covered treatment-only aborts
and delays, API removal plus successful requests, finite unrenewed fault expiry and
healthy recovery. The actual controller was killed with SIGKILL; the independent
watchdog removed the fault. Prometheus has four healthy targets; Grafana health passes.

Initial invalid/failed trials remain preserved and are listed in
`results/curated/invalid-trials.json`. Short cluster pilots and model trials are
engineering evidence, not the final comparative study or proof of novelty.

## Reproduce

Run commands from the working repository. Every run requires a **new** output path.

```sh
uv sync --frozen
uv run pytest -q
uv run ruff check src tests scripts
uv run cc-cep smoke --output results/raw/local-check-new
uv run cc-cep matrix --output results/raw/model-matrix-new
uv run cc-cep analyze results/raw/model-matrix-new
```

Install the project-local CLI tools if absent:

```sh
python3 scripts/install_tools.py
```

Create/deploy only the disposable local lab (at least 8 GiB host memory available):

```sh
docker build -f deploy/Dockerfile -t cc-cep:0.1.0 .
uv run python scripts/cluster.py create
uv run python scripts/cluster.py deploy
```

`create` refuses inadequate RAM and uses an isolated ignored kubeconfig. If the
cluster already exists, use `deploy`; do not create a second cluster. `deploy` loads the
image and applies the benchmark and observability manifests. Images are pinned; record
actual runtime IDs with `snapshot_cluster.py`. Do not redeploy during an experiment.

Validate isolation and fault safety before admitting a pilot:

```sh
uv run python -m cc_cep.cluster_smoke --output results/raw/cluster-check-new
uv run python -m cc_cep.live \
  --config experiments/cluster-pilot.json \
  --isolation results/raw/cluster-check-new/integration.json \
  --output results/raw/abort-pilot-new
uv run python -m cc_cep.live \
  --config experiments/cluster-pilot-delay.json \
  --isolation results/raw/cluster-check-new/integration.json \
  --output results/raw/delay-pilot-new
uv run cc-cep analyze results/raw/abort-pilot-new
```

The live runner gates on a recent successful isolation check, starts its own watchdog
and k6 client, and terminates its child processes. Fault administration is hardcoded to
`kind-cc-cep` / `cc-cep` and a pre-created managed VirtualService for the treatment
host. `IstioFault` will not use an arbitrary current context. The safety marker and
heartbeat are namespaced ConfigMaps. A namespace-scoped Role limits fault edits to
that VirtualService and marker; current local experiments use the isolated kind admin
kubeconfig. Running entirely as the restricted ServiceAccount remains to be validated.

Crash validation is intentionally destructive to **its own disposable experiment**:

```sh
uv run python scripts/check_controller_crash.py \
  --isolation results/raw/cluster-check-new/integration.json \
  --output results/raw/controller-crash-new
uv run python scripts/snapshot_cluster.py --output results/curated/cluster-runtime.json
```

For manual stop, create `results/tmp/EMERGENCY_STOP`. The runner checks it during warmup
and each control tick. Inspect the run's summary and verify fault removal before removing
that file for a subsequent run. Immediate known-safe restoration:

```sh
uv run python -c 'from cc_cep.istio import IstioFault; a=IstioFault(); a.clear(); assert not a.active()'
```

A stop command is not evidence of cleanup; the summary records readback. API outages can
prevent cleanup despite retries; finite Istio expiry depends on the independent watchdog
and Kubernetes API being reachable. There is no unconditional budget guarantee.

For local dashboard access, use explicit loopback port forwarding in separate terminals:

```sh
.tools/bin/kubectl --kubeconfig kubeconfig.local --context kind-cc-cep -n cc-cep port-forward service/prometheus 9090:9090 --address 127.0.0.1
.tools/bin/kubectl --kubeconfig kubeconfig.local --context kind-cc-cep -n cc-cep port-forward service/grafana 3000:3000 --address 127.0.0.1
```

Grafana has a Prometheus datasource; no publication-ready dashboard is claimed. Storage
is ephemeral with two-hour Prometheus retention. Raw client evidence is on the host.
To delete this lab after archiving evidence: `uv run python scripts/cluster.py delete`.
The cluster is left running after setup with safe routing and no experiment processes.

## Research limitations and remaining gates

The per-interval uncertainty screen is not time-uniform and accumulates clipping bias.
API readback is not exact Envoy propagation measurement. Command exposure has propagation
uncertainty. Window burn sums whole intervals ending within the window; boundaries are
quantized to the observation cadence. The client collector groups arrival at one file
boundary; it is not a distributed event-time watermark implementation. Hosts and node
resources are shared. Pilot checks do not establish causal attribution under background
errors, retries, contamination, or changing load.

The supplied pilot uses a deliberately declared two-hour reservation and a 30-second
fault window; it does not observe two hours of SLO performance. The original 60-request
allocation cannot cover the supported multi-second removal envelope. Final settings
must pass a measured feasibility gate; do not silently shrink the reserve.

Remaining before final empirical claims: healthy load-capacity/lag calibration; background
error and contamination validation; ablations; distributed controller leadership and
least-privilege execution checks; frozen pilot-calibrated open-loop cost; repeated
randomized comparative runs plus no-fault controls; paired effects/run-level confidence
intervals; final paper claim audit. Online Boutique and Chaos Mesh remain extensions.
No final comparative claims or manuscript results have been fabricated.

## Deadline schedule

- 3–5 November: prototype/safety validation, resource and capacity pilots, resolve reservation feasibility.
- 6–8 November: freeze configuration, repeated core comparisons and explicit controls/ablations.
- 9–11 November: evidence audit, reproducible paired analysis, results and threats.
- 12–14 November: report updates, figure checks, demonstration and reproduction.
- 15 November: buffer and final review. Submission: 16 November 2026.

The course brief/instructor's assessment expectations can still change this scope.
