import copy

from cc_cep.qualification import qualifies


def fixture():
    ledger = {
        "treatment_requests": 27000,
        "control_requests": 27000,
        "total_bad": 0,
        "control_bad": 0,
    }
    result = {
        "state": "COMPLETE",
        "cleanup_verified": True,
        "ledgers": {"availability": dict(ledger), "latency": dict(ledger)},
    }
    resource = {
        c: {"average_cores": 0.45, "throttled_wall_fraction": 0.01}
        for c in ("control", "treatment")
    }
    return result, resource


def test_sustained_qualification_requires_health_duration_and_cpu_headroom():
    result, resource = fixture()
    assert qualifies(result, 64, resource)
    resource["control"]["average_cores"] = 0.8
    assert not qualifies(result, 64, resource)
    result, resource = fixture()
    result["ledgers"]["latency"]["control_bad"] = 810
    assert not qualifies(result, 64, resource)


def test_screen_accepts_rare_background_errors_with_large_slo_headroom():
    result, resource = fixture()
    result["ledgers"]["availability"]["control_bad"] = 1
    result["ledgers"]["latency"]["control_bad"] = 1
    assert qualifies(result, 64, resource)
    result["ledgers"]["availability"]["control_bad"] = 140
    assert not qualifies(result, 64, resource)
    result, resource = fixture()
    result["ledgers"]["availability"]["treatment_requests"] = 100
    assert not qualifies(result, 64, resource)


def test_sustained_qualification_never_accepts_failed_or_missing_evidence():
    result, resource = fixture()
    failed = copy.deepcopy(result)
    failed["state"] = "FAILED"
    assert not qualifies(failed, 64, resource)
    assert not qualifies(result, 64, {})
    result["ledgers"] = {}
    assert not qualifies(result, 64, resource)
