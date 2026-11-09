# Final measured findings — 9 November 2026

The replacement `full-study-v7` collected all **110 selected cluster runs** with the
original 120/300/120-second phases. These are actual cluster measurements, not the
earlier simulation matrix. Four independent full-length qualifications preceded them.
Collection ended at 08:49 Pakistan time; automated analysis/artifact build exited
successfully at 09:04. All 96 core paired metric comparisons and sixteen background
comparisons are complete. Five sequential replication blocks support each contrast.

## Findings

- All ten no-fault controls recorded zero bad outcomes and zero enforcement debit.
- Every selected run had zero full-allocation overshoot. The large removal reserves
  mean this outcome alone cannot demonstrate tight control.
- Adaptive minus static latency usable-guard overshoot averaged -4.6/-21.6 requests
  for aborts at 32/64 requests/s, and -9.2/-16.2 for delays. The descriptive paired
  95% bootstrap intervals exclude zero in those four contrasts. Static delivered more
  commanded exposure. Each policy retained the same emergency guards.
- Against calibrated open-loop, adaptive delay exposure increased by about 0.8
  fraction-seconds at both loads. Adaptive abort exposure decreased by about nine
  fraction-seconds. Adaptive control does not dominate calibrated open-loop.
- Under 0.5% independent synthetic background errors, matched point estimates reduced
  absolute error against the tagged residual reference by 66.78/134.60 requests at
  32/64 requests/s. Conservative credit remained zero at 32 and averaged 25.91 at 64.
  Exposure difference intervals include zero at both loads. Better point estimates
  did not establish better exposure from the enforcement credit.

`results/curated/final-study-summary.json` derives its numbers directly from the frozen
study CSV tables. `scripts/summarize_final_study.py` regenerates it and the mean table.
The manuscript gives the numerical intervals and interprets negative findings.

## Failure and evidence accounting

There are **111 retained attempts**: 110 selected successful executions and one failed
attempt interrupted by host suspend on 8 November, 22:23–22:32 Pakistan time. Stale
telemetry triggered stopping; watchdog removal and API fault-absence readback were
observed. Draining timed out, the attempt remained failed, and its one predeclared
retry completed. Every retained attempt verified cleanup. No valid unfavorable result
was retried. Earlier superseded studies and qualifications are archived, not pooled.

The portable evidence is `results/evidence/full-study-v7/`: 111 attempt archives plus
one metadata archive, an index and SHA-256 sidecars. It includes raw k6 observations,
ledgers, configurations, source snapshots, runtime pins, qualification/pilot evidence,
recovery history and CSV analysis. Runtime credential symlinks are excluded. Preserve
all indexed parts together. A final-deliverable manifest is separate from the frozen
measurement source; paper/deck edits never rewrite experimental observations.

For GitHub distribution, the oversized metadata archive is stored as four ordered
`.part-*` files. The index records each part's checksum and the original full-archive
checksum. The current verifier reassembles and verifies it automatically. Git LFS is
not required. This packaging change does not alter measurements or analysis tables.

Reproduce after installing the locked environment, into a **new** directory:

```sh
uv sync --frozen
uv run python scripts/reproduce_evidence.py \
  --index results/evidence/full-study-v7/index.json \
  --destination results/tmp/reproduced-study-new --analyze
```

The verifier checks archive/index and internal evidence hashes, extracts safely, imports
archived measurement code, replays successful ledgers and regenerates matrix analysis.
Raw extraction uses roughly 30 GiB; allow additional room for analysis and copies.
Independent reproduction passed on 9 November at 10:23 Pakistan time: all 173 internal
manifests verified, all 110 selected runs replayed, and all seven regenerated analysis
outputs matched their originals byte for byte. See
`results/curated/portable-reproduction-result.json`. Historical stopped matrices remain
explicitly incomplete and are not pooled into the final dataset.

## Deliverables

- Report: `output/pdf/cep-report-final.pdf`.
- Editable 12-slide presentation: `output/slides/cep-research-final-v2.pptx`.
- Labelled recorded demonstration: `output/demo/cep-study-recorded-trace.mp4`.
- Overleaf-compatible source bundle: `output/cc-cep-overleaf-source.zip`.
- Implementation/report source: `output/cc-cep-implementation-source.tar.gz`.
- Complete indexed raw-evidence parts: `results/evidence/full-study-v7/`.
- Current working implementation and locked deployment: this repository; frozen
  measurement source is independently present in the study archives.

Select `cas-dc-template.tex` as the Overleaf main document, using pdfLaTeX and BibTeX.
The source bundle contains its local dependencies and generated result inserts. Earlier
interim PDFs/decks are historical. See DEMONSTRATION.md for the viva sequence. Students
should review authorship and rehearse before the 16 November submission; no rubric was
provided. No Overleaf upload or course submission has been performed. Repository commits and pushes are tracked separately in Git history.

## Scope and limits

The measured MVP covers the four policies, separate SLO ledgers, matched estimates,
synthetic background ablation, Istio targeting, cleanup and evidence replay. It does
not establish general causal attribution, production safety, or universal superiority.
Five sequential blocks on one shared node and host transport offer limited precision.
Intervals have no multiplicity adjustment and are descriptive.

Single-vs-dual-SLO and intentionally delayed-telemetry **cluster ablations were not
collected**. Unit checks establish implementation behavior only; the paper states this
limitation. Distributed leadership, Windows execution, correlated real incidents,
Online Boutique and Chaos Mesh remain unvalidated or outside the measured scope. The
oracle is retrospective sensitivity, not a proven discovery predictor.

Close prior art already describes SLO-governed fault rates and matched chaos cohorts.
This project contributes a reproducible empirical course study and a particular
accounting/control implementation. Novelty or publication acceptance is not guaranteed.
See NOVELTY.md for the primary-source audit and its non-exhaustive search limits.
