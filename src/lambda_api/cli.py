from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .audit_events import infer_instance_start_times_from_events, iter_audit_events
from .client import LambdaCloudClient
from .errors import LambdaCloudError
from .images import list_images
from .instances import (
    hours_since,
    infer_instance_start_time,
    list_instances,
    terminate_instance,
)


def _parse_kv_list(items: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"Invalid tag '{raw}'. Use KEY=VALUE")
        key, value = raw.split("=", 1)
        out.append({"key": key, "value": value})
    return out


def _parse_mount_list(items: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw in items:
        if ":" not in raw:
            raise ValueError(f"Invalid mount '{raw}'. Use /mount/point:FILESYSTEM_ID")
        mount_point, file_system_id = raw.split(":", 1)
        out.append({"mount_point": mount_point, "file_system_id": file_system_id})
    return out


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _ensure_started_at_tag(
    payload: dict[str, Any], *, tag_key: str = "started-at"
) -> None:
    tags = payload.get("tags")
    if tags is None:
        tags = []
        payload["tags"] = tags

    if not isinstance(tags, list):
        # Don't try to coerce unknown structures.
        return

    for entry in tags:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key in (tag_key, "started_at", "started-at"):
            return

    now = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    tags.append({"key": tag_key, "value": now})


def cmd_instances_launch(args: argparse.Namespace) -> int:
    payload = json.loads(_read_text_file(args.file))
    if not isinstance(payload, dict):
        raise ValueError("Launch payload must be a JSON object")

    # Make long-running checks reliable by tagging launch time automatically.
    _ensure_started_at_tag(payload)

    with LambdaCloudClient(api_key=args.api_key) as client:
        data = client.post("/instance-operations/launch", json=payload)

    _print(data, as_json=True)
    return 0


def cmd_instances_shutdown(args: argparse.Namespace) -> int:
    with LambdaCloudClient(api_key=args.api_key) as client:
        data = terminate_instance(client, instance_id=args.id)
    _print(data, as_json=True)
    return 0


def _print(obj: Any, *, as_json: bool) -> None:
    if as_json:
        try:
            print(json.dumps(obj, indent=2, sort_keys=True, default=str))
        except BrokenPipeError:
            # Common when piping to tools like `head`.
            return
    else:
        try:
            print(obj)
        except BrokenPipeError:
            return


def cmd_instances_list(args: argparse.Namespace) -> int:
    with LambdaCloudClient(api_key=args.api_key) as client:
        instances = list_instances(client)
    _print(instances, as_json=args.json)
    return 0


def cmd_images_list(args: argparse.Namespace) -> int:
    with LambdaCloudClient(api_key=args.api_key) as client:
        images = list_images(client)
    _print(images, as_json=args.json)
    return 0


def cmd_instances_long_running(args: argparse.Namespace) -> int:
    threshold_hours = float(args.hours)
    now = datetime.now(timezone.utc)

    with LambdaCloudClient(api_key=args.api_key) as client:
        instances = list_instances(client)

        instance_ids = [
            str(i.get("id")) for i in instances if isinstance(i, dict) and i.get("id")
        ]

        audit_map: dict[str, datetime] = {}
        if args.fallback_audit_events and instance_ids:
            window_start = now - timedelta(hours=float(args.audit_window_hours))
            events = iter_audit_events(
                client,
                start=window_start.isoformat().replace("+00:00", "Z"),
                end=now.isoformat().replace("+00:00", "Z"),
                resource_type=args.audit_resource_type,
                max_pages=int(args.audit_max_pages),
            )
            audit_map = infer_instance_start_times_from_events(
                events,
                instance_ids,
                action_keywords=tuple(args.audit_action_keyword),
            )

    findings: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    for inst in instances:
        if not isinstance(inst, dict):
            continue
        inst_id = str(inst.get("id", ""))
        start_time = infer_instance_start_time(
            inst,
            tag_key=args.tag_key,
            audit_event_start_time=audit_map.get(inst_id),
        )
        if start_time is None:
            unknown.append(inst)
            continue

        age_hours = hours_since(start_time, now=now)
        if age_hours >= threshold_hours:
            findings.append(
                {
                    "id": inst_id,
                    "name": inst.get("name"),
                    "status": inst.get("status"),
                    "ip": inst.get("ip"),
                    "started_at": start_time.isoformat().replace("+00:00", "Z"),
                    "age_hours": round(age_hours, 2),
                }
            )

    payload = {
        "threshold_hours": threshold_hours,
        "now": now.isoformat().replace("+00:00", "Z"),
        "long_running": findings,
        "unknown_start_time": unknown if args.include_unknown else [],
    }

    _print(payload, as_json=True if args.json else True)

    if args.fail_on_findings and findings:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lambda-api", description="Lambda Cloud API helper CLI"
    )
    p.add_argument(
        "--api-key", default=None, help="API key (or set LAMBDA_API_KEY env var)"
    )
    p.add_argument(
        "--dotenv",
        default=None,
        help="Path to a .env file to load (default: .env if present)",
    )
    p.add_argument(
        "--no-dotenv",
        action="store_true",
        help="Disable loading a .env file",
    )

    sub = p.add_subparsers(dest="command", required=True)

    instances = sub.add_parser("instances", help="Instance-related commands")
    inst_sub = instances.add_subparsers(dest="instances_cmd", required=True)

    images = sub.add_parser("images", help="Image-related commands")
    img_sub = images.add_subparsers(dest="images_cmd", required=True)

    img_list = img_sub.add_parser("list", help="List available images")
    img_list.add_argument("--json", action="store_true", help="Output JSON")
    img_list.set_defaults(func=cmd_images_list)

    inst_list = inst_sub.add_parser("list", help="List running instances")
    inst_list.add_argument("--json", action="store_true", help="Output JSON")
    inst_list.set_defaults(func=cmd_instances_list)

    inst_lr = inst_sub.add_parser(
        "long-running", help="Find instances running longer than N hours"
    )
    inst_lr.add_argument(
        "--hours", type=float, default=24.0, help="Threshold in hours (default: 24)"
    )
    inst_lr.add_argument(
        "--tag-key",
        default="started-at",
        help="Instance tag key containing ISO8601 start time",
    )
    inst_lr.add_argument(
        "--fallback-audit-events",
        action="store_true",
        help="Infer start time via audit events when tag is missing",
    )
    inst_lr.add_argument(
        "--audit-window-hours",
        type=float,
        default=24.0 * 14,
        help="How far back to look in audit events (default: 336h)",
    )
    inst_lr.add_argument(
        "--audit-resource-type",
        default="instance",
        help="Audit events resource_type filter (default: instance)",
    )
    inst_lr.add_argument(
        "--audit-max-pages", type=int, default=25, help="Max audit event pages to scan"
    )
    inst_lr.add_argument(
        "--audit-action-keyword",
        action="append",
        default=["launch", "launched", "restart", "restarted", "start", "started"],
        help="Action keyword to treat as start (repeatable)",
    )
    inst_lr.add_argument(
        "--include-unknown",
        action="store_true",
        help="Include instances where start time cannot be inferred",
    )
    inst_lr.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with code 1 if any long-running instances are found",
    )
    inst_lr.add_argument(
        "--json",
        action="store_true",
        help="Output JSON (default true for this command)",
    )
    inst_lr.set_defaults(func=cmd_instances_long_running)

    inst_launch = inst_sub.add_parser(
        "launch", help="Launch (start) an on-demand instance from a JSON file"
    )
    inst_launch.add_argument(
        "file",
        help="Path to JSON file containing the /instance-operations/launch request body",
    )
    inst_launch.set_defaults(func=cmd_instances_launch)

    inst_shutdown = inst_sub.add_parser(
        "shutdown", help="Shutdown (terminate) an instance by id"
    )
    inst_shutdown.add_argument("id", help="Instance id")
    inst_shutdown.set_defaults(func=cmd_instances_shutdown)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.no_dotenv:
        dotenv_path = args.dotenv
        if dotenv_path is None:
            default_path = Path(".env")
            dotenv_path = str(default_path) if default_path.exists() else None

        if dotenv_path:
            try:
                import importlib

                load_dotenv = importlib.import_module("dotenv").load_dotenv
                load_dotenv(dotenv_path=dotenv_path, override=False)
            except Exception:
                # Dotenv is a convenience; env vars and --api-key still work.
                pass

    try:
        return int(args.func(args))
    except LambdaCloudError as e:
        err = {
            "error": {
                "http_status": e.http_status,
                "code": e.code,
                "message": e.message,
                "suggestion": e.suggestion,
            }
        }
        print(json.dumps(err, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
