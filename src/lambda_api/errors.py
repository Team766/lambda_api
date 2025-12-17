from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class LambdaCloudError(RuntimeError):
    http_status: int
    code: str
    message: str
    suggestion: Optional[str] = None
    response_json: Optional[dict[str, Any]] = None

    def __str__(self) -> str:  # pragma: no cover
        base = f"LambdaCloudError(http_status={self.http_status}, code={self.code})"
        if self.message:
            base += f": {self.message}"
        return base
