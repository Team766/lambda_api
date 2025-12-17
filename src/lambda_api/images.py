from __future__ import annotations

from typing import Any

from .client import LambdaCloudClient


def list_images(client: LambdaCloudClient) -> list[dict[str, Any]]:
    data = client.get("/images")
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]
