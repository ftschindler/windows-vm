"""Import `.scripts/check_evidence.py` as a module.

Same reason as kit_layout.py: `.scripts` is not an importable package, and
loading the guard by path gives the tests its functions rather than only its
exit code, which is what lets them point it at a crafted tree.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = REPO_ROOT / ".scripts" / "check_evidence.py"

_spec = importlib.util.spec_from_file_location("check_evidence", _SCRIPT)
if _spec is None or _spec.loader is None:  # pragma: no cover - a broken checkout
    raise ImportError(f"cannot load {_SCRIPT}")
_module = importlib.util.module_from_spec(_spec)
sys.modules["check_evidence"] = _module
_spec.loader.exec_module(_module)

check_all = _module.check_all
check_kit = _module.check_kit
kit_files = _module.kit_files
sha256_of = _module.sha256_of
main = _module.main
SCHEMA_VERSION = _module.SCHEMA_VERSION
