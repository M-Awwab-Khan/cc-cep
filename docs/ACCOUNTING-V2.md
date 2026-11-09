# Accounting correction and scope of uncertainty

The original controller repeatedly added Wilson interval upper bounds to its consumption.
Eight healthy intervals of 200 treatment requests each charged about 30.15 requests and
triggered the 60-request allocation's 30-request reserve boundary. This was an algorithmic
error, not merely a cosmetic confidence-interval bias. Historical data stays versioned;
never replay old ledgers as though they used the corrected algorithm.

Version `realized-cumulative-v2` separates signed excess estimates, observed losses,
background-credit uncertainty, and the nonrefundable enforcement debit.

- Signed interval excess remains `treatment_bad - treatment_n * control_bad/control_n`.
- Without a validated background model, debit is cumulative observed treatment bad events.
- Under the declared stationary independent Bernoulli model, derive a simultaneous lower
  bound on the realized counterfactual organic bad count and subtract only that credit.
- Debit is the high-water mark of the resulting cumulative upper estimate. Later credit
  cannot refund spent allocation. It never exceeds cumulative treatment bad events.
- Zero observed treatment bad events imply exactly zero debit, regardless of observation
  cadence. Uncertainty widths are never consumption increments.

## Conditional sequential calculation

For control Bernoulli outcomes with fixed unknown probability p, the beta(1/2,1/2)
mixture likelihood ratio is

`M_n(p) = Beta(s+1/2,n-s+1/2) / [Beta(1/2,1/2) p^s (1-p)^(n-s)]`.

Invert `M_n(p) < 1/alpha_control` for a lower confidence sequence `p_lower`.
Ville's inequality supplies a time-uniform statement under that fixed Bernoulli model.
For the treatment counterfactual background sequence, a lower-tail Chernoff bound at
request count n with `delta_n = delta * 6/(pi*n)^2` gives

`background_lower = max(0, n*p_lower - sqrt(2*n*p_lower*log(1/delta_n)))`.

The function clipped at zero is nondecreasing in p, so using a simultaneous lower rate
bound is conservative on its coverage event. A union bound over n and the control-CS
failure event yields a joint error allocation. The implementation splits alpha equally
between the two events and across the two SLOs. The ledger's high-water mark preserves
an upper bound on nondecreasing realized induced losses on that event.

This assumes independent, identically distributed organic Bernoulli outcomes in both
cohorts, comparable eligibility, and monotone injection that cannot eliminate organic
bad outcomes. It is NOT valid for arbitrary drift, shared incidents, dependent outcomes,
or contaminated controls. The default is `background_model=unvalidated`, granting no
background credit. Only the explicitly controlled synthetic-background experiment
selects `iid-bernoulli`. The hash-seeded generator approximates the declared iid model;
this is not evidence about arbitrary real background failures.

The confidence-sequence idea is prior art: [Howard et al. (2021)](https://doi.org/10.1214/20-AOS1991).
This project does not claim a new general statistical method or general causal inference.
Future-risk prediction remains a controller heuristic. The reserve assumes the specified
traffic cap and lag envelope; API outages prevent an unconditional budget guarantee.

## Validation

- A 300-observation healthy regression now reaches duration with exactly zero debit.
- Cleanup exhaustion sets a sticky failed flag. A subsequent successful removal is
  recovery evidence; it cannot turn that failed execution into a successful trial.
- Real no-fault cluster evidence: 2,006 post-baseline treatment requests, no bad events,
  no debit, duration stop, cleanup verified, ledgers replayed from raw client outcomes.
- A seeded model validation used 200 iid replications of 100,000 requests. The retained
  JSON reports errors and inspected-time coverage, including every replication. Model
  validation is distinct from the full cluster attribution study.
