"""Sequential background credit under explicitly declared iid Bernoulli assumptions.

The beta(1/2,1/2) mixture likelihood ratio is an e-process for a fixed Bernoulli p.
Its inversion gives an anytime lower confidence sequence. A separate Chernoff lower
bound, spending delta_n = delta*6/(pi*n)^2, bounds realized counterfactual treatment
background counts simultaneously over n. Neither margin is a consumption increment.
"""

import math


def bernoulli_lower(bad: int, total: int, alpha: float):
    if not 0 < alpha < 1 or not 0 <= bad <= total:
        raise ValueError("invalid Bernoulli confidence inputs")
    if total == 0 or bad == 0:
        return 0.0
    log_mix = (
        math.lgamma(bad + 0.5)
        + math.lgamma(total - bad + 0.5)
        - math.lgamma(total + 1)
        - 2 * math.lgamma(0.5)
    )
    boundary = math.log(1 / alpha)
    low, high = 0.0, bad / total
    for _ in range(64):
        p = (low + high) / 2
        log_e = log_mix - bad * math.log(p)
        if total > bad:
            log_e -= (total - bad) * math.log1p(-p)
        if log_e > boundary:
            low = p
        else:
            high = p
    return low


def background_credit(control_bad, control_n, treatment_n, alpha=0.025):
    """Lower bound on realized counterfactual bad counts, NOT future bad events.

    Requires control and treatment organic outcomes to be independent iid Bernoulli
    with the same fixed parameter, complete eligibility counts, and no contamination.
    Coverage is joint over observation times by Ville + union bounds. No such claim
    is made for drift, interference, or correlated background failures.
    """
    p_lower = bernoulli_lower(control_bad, control_n, alpha / 2)
    if treatment_n == 0:
        return 0.0
    mean_lower = treatment_n * p_lower
    log_inverse_delta = math.log(2 / alpha) + 2 * math.log(treatment_n) + math.log(math.pi**2 / 6)
    return max(0.0, mean_lower - math.sqrt(2 * mean_lower * log_inverse_delta))
