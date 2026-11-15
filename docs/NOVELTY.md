# Research positioning audit — 3 November 2026

**Verdict: a credible empirical research question; novelty is provisional, not established.**
The engineering prototype cannot establish novelty or acceptance by itself. We have not
reproduced the manuscript's claimed Web of Science search, verified indexing/JCR claims,
or completed a systematic full-text review. The revised manuscript removes absolute gap assertions and describes a candidate
empirical contribution. A systematic full-text comparison remains a submission gate.

Candidate contribution: a controller that adjusts injected-request percentage using
separate availability/threshold-latency budget allocations, with matched-cohort excess
bad-request accounting, lag/removal reserves, and an evaluation of overshoot versus fault
exposure. Attribution is conditional on isolation and comparable traffic. It is not a
new general-purpose causal estimator. The oracle is a descriptive sensitivity summary.

## Primary-source evidence ledger

| Source | Verified evidence | Consequence and remaining limit |
| --- | --- | --- |
| [Basiri et al., A Platform for Automating Chaos Experiments (2017)](https://arxiv.org/abs/1702.05849) | Author paper record describes Netflix's failure-injection platform. | Automated chaos experimentation already exists; this abstract alone cannot establish every implementation property. |
| [Basiri et al., Automating chaos experiments in production (2019), full text](https://arxiv.org/html/1905.04648v1) | ChAP provisions baseline/canary clusters, injects failures/latency, monitors outcomes, and has safety mechanisms. | Control/treatment routing, automated termination, and fault tagging are prior art. Compare the budget-intensity algorithm specifically. |
| [Botros et al., UNFRAGILE (2024), author repository](https://keele-repository.worktribe.com/output/856761/towards-antifragility-of-cloud-systems-an-adaptive-chaos-driven-framework) | Repository identifies adaptive chaos-driven resilience research and DOI 10.1016/j.infsof.2024.107519. | Adaptive chaos is not a new category. Full algorithm comparison remains required. |
| [Souza et al., BAHYA (2026), publisher](https://www.sciencedirect.com/science/article/pii/S0167739X26002542) | Publisher abstract describes budget-aware hybrid DRL application placement. | Budget-aware optimization is prior art. Placement differs from a fault-intensity actuator; abstract review does not prove absence of related methods. |
| [Google SRE workbook, Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) | Defines error-budget burn and multiwindow alerting tradeoffs. | Count arithmetic and burn rates are established practice, not novel contributions. |
| [Istio fault-injection documentation](https://istio.io/latest/docs/tasks/traffic-management/fault-injection/) | Delay/abort request faults and scoped routing are supported. | Tool integration is an engineering artifact; it does not establish research novelty. |

Searches on 3 November 2026 included combinations of chaos engineering, SLO, error
budget, attribution, control/treatment, and adaptive fault intensity, plus exact-title
verification of nearby work. These were targeted web searches, not an exhaustive review.
The earlier acronym-only search was exploratory and provides no evidence about novelty.
Do not claim "first ever", "no study", or restrict prior art to journals to create a gap;
include conferences, preprints, and relevant industrial systems.

`reference-audit.json` records Crossref responses for the existing 21 bibliography DOIs.
Metadata resolution verifies a record, not its conclusions, publication quality, WoS
indexing, or the manuscript's comparison table. Rate-limited responses stay unverified.

## Falsifiable questions

1. At equal workload, allocation, bounds, and emergency guards, does attributed feedback
   reduce overshoot relative to static, threshold-stop, and pilot-calibrated open-loop?
2. Does it retain useful exposure rather than achieve safety simply by stopping early?
3. Under known background errors, when is excess-consumption estimation more accurate
   than total-burn accounting, and how does contamination invalidate it?
4. When do telemetry delay and uncertainty make the requested allocation infeasible?

A negative or inconclusive result is valid evidence. A failure to demonstrate an
advantage must not be presented as a successful controller evaluation.

## Closer technical disclosures found during the correction review

[Bertsch, US12511222B1 (2025)](https://patents.google.com/patent/US12511222B1/en)
describes budget/burn-constrained per-SLO injection rates and repeated updates. This
substantially overlaps the broad SLO-driven intensity idea. The paper now cites it;
only the specific implementation and measured trade-offs remain candidate contributions.

[Anand and Averdunk, US20220308972A1 (2022)](https://patents.google.com/patent/US20220308972A1/en)
describes error-budget tracking, recovery allowance and admission constraints for chaos
experiments, including availability and latency factors. Budget admission and recovery
allowances cannot be claimed as new in themselves. These records are technical research
positioning evidence; no legal-scope or patentability conclusion has been made.

The evaluation code remains frozen. This literature update does not change trial
parameters or the declared analysis, and must be retained in the final manuscript review.

## 8 November primary-source recheck and claim scope

The [Bertsch disclosure](https://patents.google.com/patent/US12511222B1/en), Fig. 12,
explicitly derives per-cycle chaos allowance from remaining SLO budget, subtracts current
chaos rate, caps against a burn-rate threshold and updates injection repeatedly. This
substantially overlaps generic SLO-governed intensity control; no novelty claim is based
on that category or on using multiple SLOs alone.

[Netflix ChAP](https://arxiv.org/html/1905.04648v1), sections III and IX-F, already
compares baseline/canary traffic and discusses noisy error counts and automatic stopping.
Our research must evaluate a particular accounting/control combination and retain
negative outcomes. Confidence sequences are established statistical tools, not a new
method invented by this project. These targeted rechecks are not an exhaustive search.

The core comparison uses the unvalidated-background default: enforcement debits total
observed treatment loss. Signed excess estimates remain descriptive there. Conditional
attributed enforcement is evaluated separately in the declared synthetic-background
ablation. Calling every core run causally attributed control would overstate the method.
