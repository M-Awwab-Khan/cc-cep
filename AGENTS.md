# Project guidance

## Purpose and current state
Cloud Computing CEP: **SLO-Aware Chaos Engineering for Cloud-Native Applications**.
The existing Introduction, Literature Review, authors, affiliations, and bibliography are student work. Preserve them unless explicitly asked to revise them.
The active Overleaf main document is `cas-dc-template.tex`, using the two-column `cas-dc` class.
Read README.md and docs/CEP-PLAN.md before implementation.

## Working rules
- Keep the root Overleaf-compatible. Do not move the class, style, bibliography, or required email thumbnail without updating and checking their references.
- Do not modify third-party class/style files. Preserve their copyright notices, README, and original manifest.
- Use the bundled cas-model2-names bibliography style and BibTeX. Keep citation keys stable.
- Never fabricate measurements, citations, DOI verification, indexing, impact factors, or novelty claims. Existing assertions are not independently verified.
- Separate planned behavior from implemented behavior and measured results.
- Record design choices and deviations in docs/DECISIONS.md; keep the plan status current.
- Pin dependency/chart/image versions when implementation starts; do not invent version numbers.
- Use namespace-scoped chaos only on an explicitly selected disposable test cluster. Never target production or all namespaces.
- Require finite fault duration, independent cleanup, telemetry freshness checks, minimum traffic, and an emergency stop.
- Shared dependencies can contaminate a control cohort. Validate isolation before claiming causal attribution.
- Track each SLO independently. Latency error budgets count requests exceeding a threshold; p95/p99 are supporting metrics.
- Preserve raw experiment data, configuration, seeds, timestamps, and failed trials; never silently omit failures.
- Do not commit credentials, kubeconfigs, cloud tokens, .env files, or local build output.

## Intended implementation layout
Create directories when their first real files are needed:
src/ (controller, accountant, attribution, fault adapters, oracle);
tests/ (meaningful mathematical, safety, integration tests);
deploy/ (cluster, benchmark, observability, scoped RBAC);
experiments/ (schemas, policies, workloads, run orchestration);
analysis/ (reproducible analysis and plots); results/ (run metadata and curated evidence).
Do not implement the full application during an initialization-only task.

## Validation
For manuscript edits, check citation keys, local dependencies, and unresolved labels.
Compile with latexmk -pdf -interaction=nonstopmode -halt-on-error cas-dc-template.tex when a TeX toolchain is available.
Otherwise explicitly report that compilation was not performed; use Overleaf for the PDF check.
For controller changes, test budget arithmetic, reset handling, missing data, stop conditions, cleanup failures, and restart behavior.
