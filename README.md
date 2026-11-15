# SLO-Aware Chaos Engineering for Cloud-Native Applications

Cloud Computing Course CEP by Muhammad Awwab Khan (SE-23051) and Muhammad Abyaz Khalid (SE-23053), NED University of Engineering and Technology.

## Current state
Implementation prototype is available: count-based dual-SLO accountant, matched-cohort
attribution, four policies, conservative admission/stopping, short/long burn windows,
cooldown, checkpointing, local HTTP benchmark, restricted Istio adapter, independent
watchdog, k6 orchestration, checksummed evidence, descriptive analysis, and empirical
cost summaries. Local and disposable-cluster safety checks and engineering pilots have
been run. These are not final comparative research results. Existing Introduction and
Literature Review are preserved. Novelty is provisional; see docs/NOVELTY.md.

Deadline: **16 November 2026**. No course rubric supplied.

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

The deadline is 16 November 2026. No course rubric or brief has been supplied. The local Docker VM has approximately 8 GiB of RAM; host memory was freed for cluster provisioning. Final comparison parameters remain provisional pending pilots.

## Interactive CEP learning lab

The separate [visualizer](visualizer/README.md) explains SLOs, budgets, attribution, fault injection, and adaptive control through a browser-only teaching simulation. Start locally with `node visualizer/serve.mjs`, then visit http://127.0.0.1:4173. It does not run the real CEP or provide experimental evidence.
