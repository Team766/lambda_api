from __future__ import annotations

import os
import sys

from lambda_api.client import LambdaCloudClient
from lambda_api.errors import LambdaCloudError


def main() -> int:
    api_key = os.environ.get("LAMBDA_API_KEY")
    if not api_key:
        print("Set LAMBDA_API_KEY to run smoke test.", file=sys.stderr)
        return 2

    try:
        with LambdaCloudClient(api_key=api_key) as client:
            # Smallest harmless call: list instances.
            data = client.get("/instances")
            print(f"OK: fetched instances (type={type(data).__name__})")
        return 0
    except LambdaCloudError as e:
        print(f"Lambda error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
