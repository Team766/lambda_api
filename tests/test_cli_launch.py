from __future__ import annotations

import json
import types
from pathlib import Path

import lambda_api.cli as cli


class _ClientStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, path: str, *, json: dict) -> dict:
        self.calls.append((path, json))
        return {"data": {"ok": True}}


class _LambdaCloudClientStub:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.client = _ClientStub()

    def __enter__(self) -> _ClientStub:
        return self.client

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_cmd_instances_launch_posts_payload_from_json_file(
    tmp_path: Path, monkeypatch
) -> None:
    payload = {
        "region_name": "us-west-1",
        "instance_type_name": "gpu_1x_a10",
        "ssh_key_names": ["key"],
        "quantity": 1,
    }
    f = tmp_path / "launch.json"
    f.write_text(json.dumps(payload), encoding="utf-8")

    stub = _LambdaCloudClientStub()

    def _factory(*args, **kwargs):
        return stub

    monkeypatch.setattr(cli, "LambdaCloudClient", _factory)

    args = types.SimpleNamespace(file=str(f), api_key=None)
    rc = cli.cmd_instances_launch(args)

    assert rc == 0
    assert len(stub.client.calls) == 1
    path, posted = stub.client.calls[0]
    assert path == "/instance-operations/launch"
    assert posted["region_name"] == payload["region_name"]
    assert posted["instance_type_name"] == payload["instance_type_name"]
    assert posted["ssh_key_names"] == payload["ssh_key_names"]
    assert posted["quantity"] == payload["quantity"]

    tags = posted.get("tags")
    assert isinstance(tags, list)
    assert any(isinstance(t, dict) and t.get("key") == "started-at" for t in tags)


def test_cmd_instances_launch_requires_json_object(tmp_path: Path, monkeypatch) -> None:
    f = tmp_path / "bad.json"
    f.write_text("[1,2,3]", encoding="utf-8")

    stub = _LambdaCloudClientStub()

    def _factory(*args, **kwargs):
        return stub

    monkeypatch.setattr(cli, "LambdaCloudClient", _factory)

    args = types.SimpleNamespace(file=str(f), api_key=None)

    try:
        cli.cmd_instances_launch(args)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Launch payload must be a JSON object" in str(e)

    assert stub.client.calls == []
