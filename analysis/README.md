# Analysis entry point

The installed analysis implementation is `src/cc_cep/analysis.py`:

```sh
uv run cc-cep analyze results/raw/simulation-matrix-02
```

It verifies input checksums, preserves run status including failed runs, writes per-SLO
CSV rows and a plot, and reports empirical signed cost per fraction-second of exposure.
It is descriptive. Do not mix model and cluster evidence or use superseded/invalid
trials from results/curated/invalid-trials.json for final inference. Paired effect
estimates and run-level confidence intervals remain required for the final study.
