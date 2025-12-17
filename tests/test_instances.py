from __future__ import annotations

from datetime import datetime, timezone

from lambda_api.instances import hours_since, infer_instance_start_time


def test_hours_since_is_positive_for_past_time() -> None:
    now = datetime(2025, 12, 16, 12, 0, 0, tzinfo=timezone.utc)
    then = datetime(2025, 12, 16, 11, 0, 0, tzinfo=timezone.utc)
    assert hours_since(then, now=now) == 1.0


def test_infer_instance_start_time_prefers_started_at_default_key_started_at_hyphen() -> (
    None
):
    inst = {
        "tags": [
            {"key": "started-at", "value": "2025-12-16T00:00:00Z"},
        ]
    }
    dt = infer_instance_start_time(inst)
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.isoformat().replace("+00:00", "Z") == "2025-12-16T00:00:00Z"


def test_infer_instance_start_time_accepts_legacy_started_at_underscore() -> None:
    inst = {
        "tags": [
            {"key": "started_at", "value": "2025-12-16T00:00:00Z"},
        ]
    }
    dt = infer_instance_start_time(inst)
    assert dt is not None
    assert dt.isoformat().replace("+00:00", "Z") == "2025-12-16T00:00:00Z"


def test_infer_instance_start_time_respects_tag_key_and_cross_falls_back() -> None:
    inst = {
        "tags": [
            {"key": "started-at", "value": "2025-12-16T00:00:00Z"},
        ]
    }
    dt = infer_instance_start_time(inst, tag_key="started_at")
    assert dt is not None
    assert dt.isoformat().replace("+00:00", "Z") == "2025-12-16T00:00:00Z"
