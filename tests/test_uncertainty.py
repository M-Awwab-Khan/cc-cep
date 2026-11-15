from cc_cep.uncertainty import background_credit, bernoulli_lower


def test_lower_bound_edges_and_large_sample_credit():
    assert bernoulli_lower(0, 0, 0.01) == 0
    assert bernoulli_lower(0, 1000, 0.01) == 0
    p = bernoulli_lower(1000, 100000, 0.01)
    assert 0 < p < 0.01
    credit = background_credit(1000, 100000, 100000)
    assert 0 < credit < 1000


def test_zero_observed_control_has_no_background_credit():
    assert background_credit(0, 100000, 100000) == 0
