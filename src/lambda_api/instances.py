from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .client import LambdaCloudClient


def list_instances(client: LambdaCloudClient) -> list[dict[str, Any]]:
    data = client.get("/instances")
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def launch_instances(
    client: LambdaCloudClient,
    *,
    region_name: str,
    instance_type_name: str,
    ssh_key_name: str,
    quantity: int = 1,
    name: Optional[str] = None,
    hostname: Optional[str] = None,
    image_id: Optional[str] = None,
    image_family: Optional[str] = None,
    file_system_names: Optional[list[str]] = None,
    file_system_mounts: Optional[list[dict[str, str]]] = None,
    user_data: Optional[str] = None,
    tags: Optional[list[dict[str, str]]] = None,
    firewall_rulesets: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "region_name": region_name,
        "instance_type_name": instance_type_name,
        "ssh_key_names": [ssh_key_name],
        "quantity": int(quantity),
    }

    if name is not None:
        payload["name"] = name
    if hostname is not None:
        payload["hostname"] = hostname

    if image_id is not None and image_family is not None:
        raise ValueError("Provide only one of image_id or image_family")
    if image_id is not None:
        payload["image"] = {"id": image_id}
    if image_family is not None:
        payload["image"] = {"family": image_family}

    if file_system_names is not None:
        payload["file_system_names"] = file_system_names
    if file_system_mounts is not None:
        payload["file_system_mounts"] = file_system_mounts
    if user_data is not None:
        payload["user_data"] = user_data
    if tags is not None:
        payload["tags"] = tags
    if firewall_rulesets is not None:
        payload["firewall_rulesets"] = firewall_rulesets

    data = client.post("/instance-operations/launch", json=payload)
    return data if isinstance(data, dict) else {"data": data}


def terminate_instance(
    client: LambdaCloudClient, *, instance_id: str
) -> dict[str, Any]:
    payload: dict[str, Any] = {"instance_ids": [str(instance_id)]}
    data = client.post("/instance-operations/terminate", json=payload)
    return data if isinstance(data, dict) else {"data": data}


def _parse_iso8601(value: str) -> Optional[datetime]:
    # Handles "2025-09-15T10:30:45.123456Z" (docs sample) and offsets.
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _get_tag_value(instance: dict[str, Any], key: str) -> Optional[str]:
    tags = instance.get("tags")
    if not isinstance(tags, list):
        return None
    for entry in tags:
        if not isinstance(entry, dict):
            continue
        if entry.get("key") == key:
            v = entry.get("value")
            return str(v) if v is not None else None
    return None


def infer_instance_start_time(
    instance: dict[str, Any],
    *,
    tag_key: str = "started-at",
    audit_event_start_time: Optional[datetime] = None,
) -> Optional[datetime]:
    tag_val = _get_tag_value(instance, tag_key)
    if not tag_val:
        # Backward/compat: allow callers to use either hyphen or underscore.
        if tag_key == "started-at":
            tag_val = _get_tag_value(instance, "started_at")
        elif tag_key == "started_at":
            tag_val = _get_tag_value(instance, "started-at")
    if tag_val:
        parsed = _parse_iso8601(tag_val)
        if parsed is not None:
            return parsed

    # Fallback: caller may provide a start time inferred from audit events
    return audit_event_start_time


def hours_since(dt: datetime, *, now: Optional[datetime] = None) -> float:
    now_dt = now or datetime.now(timezone.utc)
    return (now_dt - dt).total_seconds() / 3600.0
