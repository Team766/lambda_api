from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from .client import LambdaCloudClient


def _parse_iso8601(value: str) -> Optional[datetime]:
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def iter_audit_events(
    client: LambdaCloudClient,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    resource_type: Optional[str] = None,
    max_pages: int = 25,
) -> Iterable[dict[str, Any]]:
    page_token: Optional[str] = None
    for _ in range(max_pages):
        params: dict[str, Any] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if page_token:
            params["page_token"] = page_token
        if resource_type:
            params["resource_type"] = resource_type

        data = client.get("/audit-events", params=params)
        if not isinstance(data, dict):
            return

        events = data.get("events")
        if isinstance(events, list):
            for event in events:
                if isinstance(event, dict):
                    yield event

        page_token_val = data.get("page_token")
        page_token = str(page_token_val) if page_token_val else None
        if not page_token:
            return


def infer_instance_start_times_from_events(
    events: Iterable[dict[str, Any]],
    instance_ids: Iterable[str],
    *,
    action_keywords: tuple[str, ...] = (
        "launch",
        "launched",
        "start",
        "started",
        "restart",
        "restarted",
    ),
) -> Dict[str, datetime]:
    # Heuristic: for each instance id, pick the most recent matching event_time.
    # We match if the id appears in resource_lrns or additional_details values.
    ids = [i for i in instance_ids if i]
    latest: Dict[str, datetime] = {}

    for event in events:
        action = str(event.get("action", "")).lower()
        if action and not any(k in action for k in action_keywords):
            continue

        event_time_raw = event.get("event_time")
        if not isinstance(event_time_raw, str):
            continue
        event_time = _parse_iso8601(event_time_raw)
        if event_time is None:
            continue

        resource_lrns = event.get("resource_lrns")
        details = event.get("additional_details")

        for instance_id in ids:
            matched = False

            if isinstance(resource_lrns, list):
                for lrn in resource_lrns:
                    if isinstance(lrn, str) and instance_id in lrn:
                        matched = True
                        break

            if not matched and isinstance(details, dict):
                for v in details.values():
                    if isinstance(v, str) and instance_id in v:
                        matched = True
                        break

            if not matched:
                continue

            prev = latest.get(instance_id)
            if prev is None or event_time > prev:
                latest[instance_id] = event_time

    return latest
