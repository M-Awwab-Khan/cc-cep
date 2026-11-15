> **Completed 9 November:** all 110 selected runs verified; analysis and artifact build exited successfully. Do not resume the completed queue. See FINAL-RESULTS.md for findings and reproduction. The launch instructions below are historical.

> Current final candidate: qualification-03 / full-study-v7. Earlier named runs below
> are historical. active-study.json gives the actual PID, stage and heartbeat/status
> paths. Four fresh full phases at 32/64 requests/s must pass on the final code before
> 110 comparisons/controls/ablations. Expected phase time remains about 17.3 hours.

> Historical 8 November candidate: qualification-02 / full-study-v6. The earlier zero-event
> pilot gate is superseded by per-stream 99% Wilson upper screening limits below half
> the SLO bad fractions. Four fresh full-length qualifications must pass before the new
> 110-trial comparison. See RESEARCH-STATUS.md and active-study.json. Earlier operational
> history below remains for provenance; do not launch v3/v4/v5.

> Historical operation: v4 also reproduced stalls during warmup. It is stopped and
> superseded. scripts/qualify_and_study.py runs four predeclared no-fault qualifications
> at 32/64 requests/s and starts a fresh v5 only if all pass. Previous instructions
> below are retained as versioned operational history, not a command to resume v4.
> Check results/curated/active-study.json for the live stage and heartbeat/status path.

# Full-duration one-off study

The user selected the complete phase durations and confirmed that the machine can stay
on. This is a single sequential experiment process, not a recurring automation.

1. Sync locked dependencies and pass `uv run pytest -q` / lint.
2. Keep Docker, the disposable `kind-cc-cep` cluster and this host awake.
3. Freeze source, independent pilot costs and randomized order:

```sh
uv run python -m cc_cep.study prepare \
  --directory results/raw/full-study-v3 \
  --calibration results/raw/revision-capacity-02/selected-loads.json \
  --pilot-abort results/raw/revision-cost-abort-01 \
  --pilot-delay results/raw/revision-cost-delay-01
```

The frozen source is under that directory's `frozen/`. It deliberately links to the
local tools and ignored kubeconfig at runtime; those links are excluded from portable
archives. Controller target locks use the shared original results/tmp directory.
The exact prepared plan.json is immutable. matrix.json records attempts and selection
according to the predeclared invalid-execution retry rule.

Launch/resume using the recorded frozen source, not an edited working-tree controller:

```sh
PYTHONPATH="$PWD/results/raw/full-study-v3/frozen/src" .venv/bin/python \
  -m cc_cep.study execute --directory "$PWD/results/raw/full-study-v3"
```

The session launch uses a detached subprocess with stdout in driver.log and PID/status
in status.json. Check the recorded process identity before starting another copy. A
study-driver lock refuses duplicate execution. The runner refreshes its heartbeat every
15 seconds, retains every invalid attempt, performs a fresh isolation check periodically,
and refuses another injection after unverified cleanup. SIGTERM stops through the
controller's cleanup path; SIGKILL relies on the independently bounded watchdog.

`status.json` reports active job, completed job count, heartbeat and error. Review
`driver.log`, each attempt's summary, and any `*-error.txt`. One retry is allowed for
invalid execution/admission/replay, never because a valid result is unfavorable. An
interrupted attempt retains its partial evidence and cannot be silently marked complete.
Resume handles only recorded child PIDs with matching Linux start-time tokens.

After collection, the frozen analysis verifies raw manifests, replays each successful
ledger, reconciles raw cohort counts, and writes trials.csv, outcomes.csv,
paired-comparisons.csv, background-comparisons.csv, oracle.csv and plots. Missing blocks
leave confidence intervals incomplete. The report builder writes a study draft and
portable per-attempt archives plus a metadata bundle/index under results/evidence.
The final state explicitly requires review and never declares the CEP complete.

Reproduce a complete multi-part archive on another checkout/machine after syncing deps:

```sh
uv sync --frozen
uv run python scripts/reproduce_evidence.py \
  --index results/evidence/full-study-v3/index.json \
  --destination results/tmp/reproduced-study-new --analyze
```

The verifier checks the index and each archive, extracts safely, verifies every retained
manifest, and imports archived source for replay/analysis when present. The original
development archive remains available independently. Compiled PDFs/PPTX/video are local
outputs; the paper/slides need final content/visual review after the real study finishes.

Do not redeploy or run another live demo while collection is active. The normal emergency
stop file is results/tmp/EMERGENCY_STOP. The runner halts before another trial if fewer
than 10 GiB remain free. There is no cloud spend. Full main collection is about 14 hours;
20 ablations add roughly three hours, excluding retries and artifact packaging.

The stopped v2 batch is retained as failed admission evidence; see docs/DECISIONS.md.
The v3 driver halts for diagnosis if one trial exhausts its invalid-execution retries.

## Recovery after the invalid high-load trial

The original v3 queue is retained stopped. After both independent full-length diagnostics
pass, prepare an explicit administrative recovery; this does not replace failed evidence:

```sh
uv run python -m cc_cep.recovery \
  --previous results/raw/full-study-v3 --directory results/raw/full-study-v4 \
  --job core-delay-112-threshold-1001 \
  --healthy results/raw/high-load-diagnosis-01/trial \
  --faulted results/raw/high-load-fault-diagnosis-01/trial
```

The recovery plan permits one additional attempt solely for that invalid exhausted job;
valid comparisons are retained without rerunning them. See recovery-amendment.json and
DECISIONS.md for the post-failure protocol deviation. Launch using v4's frozen source
and directory, with the same detached process pattern. `completed_jobs` counts successful
jobs; `attempted_jobs` includes failures. Original v3 status files stay unmodified.
Resource context is in resource-context.jsonl. Do not render slides/reports or perform
capacity probes while collection is active. A diagnostic pass is not proof that the
underlying transient issue is fixed; recurring invalid execution still halts the queue.

On this Linux desktop, the resumed v4 process runs under `systemd-inhibit` with
`--what=idle:sleep --mode=block`. This prevents automatic idle/sleep during collection,
not an explicit shutdown or Docker stop. The driver PID is in status.json; the separate
supervisor PID is recorded in results/curated/active-study.json. Stop the driver through
SIGTERM for cleanup; the inhibitor releases when it exits. A prior API-unavailable
launch is retained before the RESUMED_AFTER_CLUSTER_RESTART marker in driver.log.
