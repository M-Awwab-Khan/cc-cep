import json

from cc_cep.live import OutcomeReader


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
