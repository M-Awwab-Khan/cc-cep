from cc_cep.core import SLO, Config
from cc_cep.study import make_plan


def test_runtime_anchor_detects_deployment_and_image_drift(monkeypatch):
    from cc_cep import study

    names = ("frontend-control", "frontend-treatment", "dependency-control", "dependency-treatment")
    pods = [
        {
            "name": name + "-pod",
            "containers": [
                {"name": "app", "image_id": "app-sha", "ready": True},
                {"name": "istio-proxy", "image_id": "proxy-sha", "ready": True},
            ],
        }
        for name in names
    ]
    monkeypatch.setattr(study, "cluster_inventory", lambda _: pods)

    class Adapter:
        image = "version-a"

        def _run(self, *args):
            return {"spec": {"template": {"spec": {"image": self.image}}}}

    adapter = Adapter()
    original = study.runtime_fingerprint(adapter)
    adapter.image = "version-b"
    assert study.runtime_fingerprint(adapter) != original
    adapter.image = "version-a"
    pods[0]["containers"][0]["image_id"] = "new-sha"
    assert study.runtime_fingerprint(adapter) != original


def test_full_protocol_counts_and_no_evaluation_pilot_seed_overlap():
    plan = make_plan((48, 112), {"abort": 1.1, "delay": 1.0})
    assert len(plan["jobs"]) == 110
    assert sum(j["kind"] == "core" for j in plan["jobs"]) == 80
    assert sum(j["kind"] == "control" for j in plan["jobs"]) == 10
    assert sum(j["kind"] == "background" for j in plan["jobs"]) == 20
    for job in plan["jobs"]:
        cfg = dict(job["config"]["controller"])
        cfg["slos"] = tuple(SLO(**s) for s in cfg["slos"])
        controller = Config(**cfg)
        assert controller.duration == 300
        assert job["config"]["warmup_seconds"] == job["config"]["recovery_seconds"] == 120
        assert job["seed"] >= 1001
        assert all(
            s.q * controller.expected_treatment_requests * s.allocation_fraction
            > controller.max_rps * controller.reserve_seconds
            for s in controller.slos
        )
    assert plan["jobs"] == make_plan((48, 112), {"abort": 1.1, "delay": 1.0})["jobs"]
