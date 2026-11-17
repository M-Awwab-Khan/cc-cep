# Chaos Lab learning visualizer

Interactive, browser-only companion for the SLO-aware chaos engineering CEP.
Run `node serve.mjs` here and visit http://127.0.0.1:4173.
Run `node --test model.test.mjs` for mathematical/model checks.
Open dist/index.html through a static server (ES modules require HTTP).

## Included
Live seeded simulation; separate availability/latency ledgers; delay and abort faults; fixed, threshold, preplanned, adaptive, and budget-paced policies; a selectable accounting mode (teaching point estimate, repository `realized-cumulative-v2` debit, v2 plus iid background credit, and the retired v1 Wilson charge for contrast); matched policy comparison; a Real study results page (frozen `full-study-v7` summary, including the retained failed attempt and limitations, plus the separate budget-paced follow-up), glossary, guided tour, learning journey, quiz, accessible chart data, and JSON export.

## Boundaries
This does not invoke Python, Docker, Kubernetes, Istio, or real CEP experiments.
120-second declared reservation; at most 60 seconds of synthetic observations.
The point-estimate teaching mode is the default. Repository v2 modes port `src/cc_cep/core.py` accounting and `uncertainty.py` (checked against Python outputs in the tests). The retired v1 mode reproduces the old per-interval Wilson charge and its false spending under zero observed failures.
The paced policy is a simplified port of `Controller.pace` and `_paced_step` with instant observations and a 60-second horizon; its 20-run follow-up evidence is shown only on the results page. The adaptive logic is inspired by the prototype, with simplified current-tick burn decisions rather than its multiwindow history. All observations and actuation are immediate. The reserve is arithmetic, not a simulated cleanup tail or a guarantee.
Changing traffic during a run never expands the admitted budget. A rise above the admitted RPS cap stops the run.
The preplanned baseline uses an illustrative cost, not a calibrated cluster estimate.
Do not use these outputs as research measurements, final comparison results, or proof of causal attribution.


## Study data
`dist/study-data.mjs` is generated, not hand-edited. Regenerate from the repository root with `python visualizer/tools/build_study_data.py`; it reads `results/curated/final-study-summary.json` and `results/curated/followup-table.tex` and never modifies measurements. The Real study results page is separate from the simulator: nothing in the browser model is a measurement. Verify prose findings against the manuscript before citing.
