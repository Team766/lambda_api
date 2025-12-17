from __future__ import annotations

import sys
from pathlib import Path


# Allow `import lambda_api` without requiring an editable install.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
