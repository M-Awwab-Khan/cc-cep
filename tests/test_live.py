import json

from cc_cep.live import OutcomeReader, cluster_inventory, fresh_clients, shutdown_workloads


def test_freshness_uses_decision_time_and_rejects_future_cohort_timestamps():
    assert fresh_clients({"control": 100, "treatment": 100}, 101, 5)
    assert not fresh_clients({"control": 100, "treatment": 100}, 106, 5)
    assert not fresh_clients({"control": 100, "treatment": 102}, 101, 5)


def test_replay_rejects_a_decision_made_with_stale_observations():
    import pytest

    from cc_cep.replay import verify_decision_clock

    event = {
        "decision_timestamp": 101,
        "client_latest": {"control": 100, "treatment": 100},
        "watchdog_timestamp": 100.5,
        "snapshot": {"timestamp": 100},
    }
    verify_decision_clock(event, 5)
    event["decision_timestamp"] = 106
    with pytest.raises(ValueError, match="telemetry"):
        verify_decision_clock(event, 5)


def test_exception_shutdown_clears_before_stopping_load_and_keeps_watchdog():
    calls = []

    class Controller:
        def cleanup(self, adapter):
            calls.append("cleanup")
            return False

    class Process:
        def poll(self):
            return None

        def terminate(self):
            calls.append("stop-load")

        def wait(self, timeout=None):
            return 0

    load, watchdog = Process(), Process()
    assert not shutdown_workloads(Controller(), None, [load, watchdog], watchdog)
    assert calls == ["cleanup", "stop-load"]


def test_inventory_tracks_regular_and_native_istio_sidecars():
    class Adapter:
        native = False

        def _run(self, *args):
            app = {"name": "app", "ready": True, "imageID": "app:sha", "restartCount": 0}
            proxy = {
                "name": "istio-proxy",
                "ready": True,
                "imageID": "proxy:sha",
                "restartCount": 0,
            }
            return {
                "items": [
                    {
                        "metadata": {"name": "pod", "uid": "identity"},
                        "status": {
                            "containerStatuses": [app] if self.native else [app, proxy],
                            "initContainerStatuses": [proxy, {"name": "istio-init", "ready": True}]
                            if self.native
                            else [],
                        },
                    }
                ]
            }

    adapter = Adapter()
    regular = cluster_inventory(adapter)
    adapter.native = True
    assert cluster_inventory(adapter) == regular
    assert {c["name"] for c in regular[0]["containers"]} == {"app", "istio-proxy"}


def point(cohort, value):
    return (
        json.dumps(
            {
                "type": "Point",
                "metric": "cc_outcome",
                "data": {
                    "tags": {"cohort": cohort},
                    "value": value,
                    "time": "2026-11-03T10:00:00.123456789Z",
                },
            }
        )
        + "\n"
    )


def test_outcomes_are_counted_once_and_partial_lines_wait(tmp_path):
    path = tmp_path / "raw.jsonl"
    first = point("treatment", 2)
    path.write_text(first + point("control", 0) + point("treatment", 1)[:20])
    reader = OutcomeReader(path)
    c, t = reader.read()
    assert c.total == t.total == 1
    assert t.availability == t.latency == 1
    with path.open("a") as stream:
        stream.write(point("treatment", 1)[20:])
    c, t = reader.read()
    assert t.total == 2 and t.availability == 1 and t.latency == 2
    assert reader.read() == [c, t]
    reader.close()


def test_dropped_load_invalidates_observation(tmp_path):
    import pytest

    path = tmp_path / "raw.jsonl"
    path.write_text(
        json.dumps({"type": "Point", "metric": "dropped_iterations", "data": {"value": 1}}) + "\n"
    )
    reader = OutcomeReader(path)
    with pytest.raises(ValueError, match="dropped"):
        reader.read()
    reader.close()
