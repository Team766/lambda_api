from __future__ import annotations

from lambda_api.images import list_images


class _ClientStub:
    def __init__(self, response):
        self.response = response
        self.calls: list[str] = []

    def get(self, path: str):
        self.calls.append(path)
        return self.response


def test_list_images_returns_only_dict_entries() -> None:
    client = _ClientStub(
        [
            {"id": "1"},
            "nope",
            123,
            {"id": "2"},
        ]
    )
    out = list_images(client)  # type: ignore[arg-type]
    assert out == [{"id": "1"}, {"id": "2"}]
    assert client.calls == ["/images"]


def test_list_images_non_list_returns_empty() -> None:
    client = _ClientStub({"data": []})
    out = list_images(client)  # type: ignore[arg-type]
    assert out == []
    assert client.calls == ["/images"]
