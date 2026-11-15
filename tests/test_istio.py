import copy

import pytest

from cc_cep.istio import HOST, PREFIX, IstioFault, safe_spec
from cc_cep.watchdog import step


class Fake(IstioFault):
    def __init__(self):
        super().__init__(clock=lambda: 100)
        self.object = {
            "metadata": {
                "resourceVersion": "1",
                "annotations": {},
                "labels": {PREFIX + "managed": "true"},
            },
            "spec": safe_spec(),
        }
        self.disposable = True
        self.heartbeat = 0

    def beat(self, now):
        self.heartbeat = now

    def _run(self, *args, payload=None):
        if args[:2] == ("get", "configmap"):
            return {
                "metadata": {
                    "labels": {PREFIX + "disposable": str(self.disposable).lower()},
                    "annotations": {PREFIX + "watchdog": str(self.heartbeat)},
                }
            }
        if args[0] == "get":
            return copy.deepcopy(self.object)
        import json

        operations = json.loads(args[args.index("-p") + 1])
        assert operations[0]["value"] == self.object["metadata"]["resourceVersion"]
        self.object["spec"] = operations[1]["value"]
        self.object["metadata"]["annotations"] = operations[2]["value"]
        return copy.deepcopy(self.object)


def test_watchdog_required_and_expiry_removes_fault():
    adapter = Fake()
    with pytest.raises(RuntimeError, match="heartbeat"):
        adapter.apply(0.1)
    step(adapter)
    adapter.apply(0.1)
    assert adapter.active()
    adapter.clock = lambda: 106
    assert step(adapter) == "expired fault removed"
    assert not adapter.active()


def test_non_disposable_or_wrong_host_rejected():
    adapter = Fake()
    adapter.disposable = False
    with pytest.raises(RuntimeError, match="disposable"):
        adapter.clear()
    adapter.disposable = True
    adapter.object["spec"]["hosts"] = ["other"]
    with pytest.raises(RuntimeError, match="host"):
        adapter.clear()
    assert HOST.endswith(".cc-cep.svc.cluster.local")


def test_slow_api_cannot_apply_fault_after_client_telemetry_expires():
    adapter = Fake()
    step(adapter)
    original_inspect = adapter.inspect

    def delayed_inspection():
        resource = original_inspect()
        adapter.clock = lambda: 106
        adapter.last_watchdog = 106
        return resource

    adapter.inspect = delayed_inspection
    with pytest.raises(RuntimeError, match="telemetry expired"):
        adapter.apply(0.1, telemetry_deadline=105)
    assert adapter.object["spec"] == safe_spec()
