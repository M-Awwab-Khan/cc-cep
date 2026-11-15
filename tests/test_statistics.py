from cc_cep.statistics import paired_interval


def test_missing_effective_metadata_cannot_count_as_verified_complete(tmp_path, monkeypatch):
    import json

    from cc_cep import statistics

    job = {"id": "test", "directory": "trial", "attempts": [], "kind": "core"}
    (tmp_path / "matrix.json").write_text(json.dumps({"jobs": [job], "loads": [32], "seeds": [1]}))
    (tmp_path / "trial").mkdir()
    (tmp_path / "trial/metadata.json").write_text("{}")
    monkeypatch.setattr(
        statistics,
        "verify",
        lambda _: {
            "state": "COMPLETE",
            "cleanup_verified": True,
            "stop_reason": "duration",
            "ledgers": {},
        },
    )
    monkeypatch.setattr(statistics, "replay", lambda _: {"state": "COMPLETE"})
    result = statistics.analyze_matrix(tmp_path)
    assert result["verified_complete"] == 0
    assert result["failed_or_unverified"] == 1


def test_exact_constant_paired_difference():
    result = paired_interval({1: 2, 2: 2, 3: 2, 4: 2, 5: 2}, [1, 2, 3, 4, 5])
    assert result["complete"]
    assert result["mean_difference"] == result["ci_low"] == result["ci_high"] == 2


def test_missing_failed_block_cannot_disappear_from_inference():
    result = paired_interval({1: 1, 2: 2}, [1, 2, 3, 4, 5])
    assert not result["complete"]
    assert result["missing_blocks"] == [3, 4, 5]
    assert result["ci_low"] is None
