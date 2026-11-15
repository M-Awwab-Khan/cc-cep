"""Seeded controlled-background validation; explicitly model evidence, not cluster runs."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from cc_cep.core import Config, Controller, Counts, Snapshot


def main():
    rng = np.random.default_rng(20261103)
    rows = []
    for seed in range(200):
        config = replace(
            Config(),
            expected_treatment_requests=10000000,
            max_rps=2000,
            background_model="iid-bernoulli",
            duration=1000,
        )
        controller = Controller(config)
        controller.admit(Snapshot(0, str(seed), Counts(1000, 0, 0), Counts(1000, 0, 0)), 0)
        control_n = treatment_n = 1000
        c_bad = t_bad = organic = 0
        covers = True
        for tick in range(1, 101):
            control = int(rng.binomial(1000, 0.005))
            treatment_bg = int(rng.binomial(1000, 0.005))
            induced = int(rng.binomial(1000 - treatment_bg, 0.01))
            control_n += 1000
            treatment_n += 1000
            c_bad += control
            organic += treatment_bg
            t_bad += treatment_bg + induced
            controller.account_tail(
                Snapshot(
                    tick,
                    str(seed),
                    Counts(control_n, c_bad, c_bad),
                    Counts(treatment_n, t_bad, t_bad),
                ),
                tick,
            )
            covers &= controller.ledgers["availability"].enforced >= t_bad - organic
        ledger = controller.ledgers["availability"]
        rows.append(
            {
                "seed": seed,
                "point_error": abs(ledger.signed - (t_bad - organic)),
                "total_error": organic,
                "all_times_enforcement_covers_reference": bool(covers),
                "background_lower": ledger.background_lower,
                "reference": t_bad - organic,
                "signed": ledger.signed,
                "enforced": ledger.enforced,
            }
        )
    output = Path("results/curated/attribution-model-validation.json")
    output.write_text(
        json.dumps(
            {
                "mode": "iid-bernoulli-model-validation",
                "seed": 20261103,
                "replications": 200,
                "observations_per_replication": 100000,
                "mean_point_absolute_error": float(np.mean([r["point_error"] for r in rows])),
                "mean_total_absolute_error": float(np.mean([r["total_error"] for r in rows])),
                "all_times_coverage_replicates": sum(
                    r["all_times_enforcement_covers_reference"] for r in rows
                ),
                "limitation": "Independent stationary Bernoulli generator; does not establish field causal validity",
                "runs": rows,
            },
            indent=2,
        )
        + "\n"
    )
    print(output)


if __name__ == "__main__":
    main()
