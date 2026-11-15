# Chaos Lab learning visualizer

Interactive, browser-only companion for the SLO-aware chaos engineering CEP.
Run `node serve.mjs` here and visit http://127.0.0.1:4173.
Run `node --test model.test.mjs` for mathematical/model checks.
Open dist/index.html through a static server (ES modules require HTTP).

## Included
Live seeded simulation; separate availability/latency ledgers; delay and abort faults; fixed, threshold, preplanned, and adaptive policies; a repository Wilson-screen demonstration; matched policy comparison; glossary, guided tour, learning journey, quiz, accessible chart data, and JSON export.

## Boundaries
This does not invoke Python, Docker, Kubernetes, Istio, or real CEP experiments.
120-second declared reservation; at most 60 seconds of synthetic observations.
The point-estimate teaching mode is the default. Optional Wilson mode ports the prototype formula, including its false spending under zero observed failures.
The adaptive logic is inspired by the prototype, with simplified current-tick burn decisions rather than its multiwindow history. All observations and actuation are immediate. The reserve is arithmetic, not a simulated cleanup tail or a guarantee.
Changing traffic during a run never expands the admitted budget. A rise above the admitted RPS cap stops the run.
The preplanned baseline uses an illustrative cost, not a calibrated cluster estimate.
Do not use these outputs as research measurements, final comparison results, or proof of causal attribution.

