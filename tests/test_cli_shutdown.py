from __future__ import annotations

import types

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


def test_cmd_instances_shutdown_posts_instance_id(monkeypatch) -> None:
    stub = _LambdaCloudClientStub()

    def _factory(*args, **kwargs):
        return stub

    monkeypatch.setattr(cli, "LambdaCloudClient", _factory)

    args = types.SimpleNamespace(id="abc123", api_key=None)
    rc = cli.cmd_instances_shutdown(args)

    assert rc == 0
    assert stub.client.calls == [
        (
            "/instance-operations/terminate",
            {"instance_ids": ["abc123"]},
        )
    ]
