# SLO-Aware Chaos Engineering for Cloud-Native Applications

Cloud Computing Course CEP by Muhammad Awwab Khan (SE-23051) and Muhammad Abyaz Khalid (SE-23053), NED University of Engineering and Technology.

## Current state
The full-duration cluster study completed on **9 November 2026**: 80 core comparisons,
10 no-fault controls and 20 background-error ablations, with 110 verified selected runs.
All 96 core paired metric comparisons and 16 background comparisons are available.
One sleep-interrupted attempt failed and its declared retry passed; both are retained.
See [final findings](docs/FINAL-RESULTS.md) and [research status](docs/RESEARCH-STATUS.md).

The implementation provides separate count-based SLO ledgers, matched-cohort estimates,
four policies, bounded Istio faults, an independent watchdog and evidence replay. The
manuscript reports mixed findings: adaptive control reduces usable-guard overshoot versus
static injection, but calibrated open-loop delivers substantially more abort exposure.
Broad SLO-driven injection has close prior art; this is an empirical course contribution.
See docs/NOVELTY.md. Student authors and vendor layout files are preserved.

Deadline: **16 November 2026**. The course brief and rubric arrived on 15 November; see
[rubric coverage](docs/RUBRIC-MATRIX.md). Print `rubric-cover.tex` (title page and filled
rubric) on top of the report.

Quick start (from this project directory):

```sh
uv sync --frozen
uv run pytest -q
uv run cc-cep smoke --output results/raw/my-local-check
uv run cc-cep simulate --output results/raw/my-model-run
uv run cc-cep analyze results/raw/my-model-run
```

Use a new output directory for each execution. The committed `uv.lock` pins Python
packages; project-local CLI versions and publisher/binary checksums are recorded in
`deploy/tools.lock.json`. Tools live under ignored `.tools/bin`.

- [Implementation/runbook](docs/IMPLEMENTATION.md)
- [Research/novelty audit](docs/NOVELTY.md)
- [Pilot/evaluation protocol](experiments/PROTOCOL.md)
- [Verification evidence](results/curated/)

The dedicated local cluster is `kind-cc-cep`; its kubeconfig is ignored and local.
No cloud resources or spending are used.

The full-study metadata archive is distributed as four `.part-*` files to fit GitHub's
regular-file limit. Keep all indexed parts together. The current portable verifier
checks each part and reassembles the original archive automatically; Git LFS is not
required. Reassembly preserves the archive's original SHA-256. Packaging checks add
three tests to the original 59-test suite, for 62 passing tests.

## Review corrections and full study

The interval-Wilson consumption defect is fixed in `realized-cumulative-v2`: zero bad
requests consume zero budget. Conditional background credit uses a separate sequential
calculation; the default grants no credit without the declared model. Cleanup exhaustion
sets a sticky failed flag. A later successful removal cannot mark that execution successful.

The original development archive is now included under `results/evidence/` with an
external SHA-256 file. Verify its 169 internal manifests without third-party packages:

```sh
python scripts/reproduce_evidence.py --archive results/evidence/implementation-2026-11-03.tar.gz --destination results/tmp/original-evidence-new
```

See [accounting details](docs/ACCOUNTING-V2.md), [full-duration frozen protocol](experiments/FULL-STUDY.md),
[demonstration](docs/DEMONSTRATION.md), and [long-run operation](docs/FULL-STUDY-RUNBOOK.md).
The user explicitly retained 120/300/120-second phases. The main 90 trials need roughly
14 hours; 20 background ablations add roughly three hours. Statistical code is ready;
cluster inference and measured conclusions are now available in the final findings.

Native Windows unit-test collection no longer imports `fcntl` unconditionally. Install
the locked dependencies with `uv sync --frozen` before testing. A Windows/Linux CI workflow
is provided, but Windows execution has not been performed in this session. Cluster setup,
crash/recovery supervision and the current binary installer still require Linux/WSL.

The correction archive `results/evidence/revision-2026-11-03.tar.gz` retains source,
revised pilots, and the stopped v2 admission failures. Its portable verification checked
195 internal manifests and replayed revised successful ledgers against raw client counts.
It deliberately excludes the actively changing v3 study, which receives its own bundles
after collection. The 8 November audit suite has 59 passing tests.

The final report, editable 12-slide deck and labelled recorded-trace demonstration are
under ignored `output/`. Earlier interim artifacts remain for provenance; use the
paths in docs/FINAL-RESULTS.md for the final study deliverables.

## Overleaf
Upload the project source and choose **cas-dc-template.tex** as the Main document in Overleaf settings. Use **pdfLaTeX** and BibTeX with an available current TeX Live release. The manuscript uses Elsevier's two-column CAS class.

Required local files:
- cas-dc-template.tex: manuscript.
- cas-dc.cls and cas-common.sty: original vendor layout files.
- cas-model2-names.bst: bundled bibliography style.
- cas-refs.bib: existing research references.
- thumbnails/cas-email.jpeg: used by the author email footer.

The original vendor README and manifest are retained for provenance; the manifest describes the upstream distribution, including removed examples. Sample PDFs, alternative single-column templates, sample figures, and vendor documentation sources have been removed.

After upload, use Recompile from scratch and inspect the log, bibliography, author notes, and wide comparison table. Local cleanup does not synchronize an existing Overleaf project automatically. No Overleaf account or remote project is connected in this workspace.

## Local PDF build
Install a TeX distribution with latexmk, then run:

~~~powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error cas-dc-template.tex
~~~

Without latexmk, run pdfLaTeX, BibTeX, pdfLaTeX, pdfLaTeX on the manuscript basename.
Do not commit generated PDF/build files. The vendor .cls/.sty/.bst files retain their upstream licenses.

## Project work
- [Agent guidance](AGENTS.md)
- [Complete CEP plan](docs/CEP-PLAN.md)
- [Decisions and assumptions](docs/DECISIONS.md)

The qualification-03 / full-study-v7 process finished successfully on 9 November.
Source, runtime pins and all failed attempts remain in the evidence. No experiment
process remains active. The disposable cluster is left available with fault-free routing.
See docs/FINAL-RESULTS.md for reproduction commands and limitations. Earlier runbook
commands are historical; do not restart a completed study or overwrite its observations.

## Interactive CEP learning lab

The separate [visualizer](visualizer/README.md) explains SLOs, budgets, attribution, fault injection, and adaptive control through a browser-only teaching simulation. Start locally with `node visualizer/serve.mjs`, then visit http://127.0.0.1:4173. It does not run the real CEP or provide experimental evidence.
