"""Import `.scripts/check_kit_layout.py` as a module.

The guard is a script with a hyphen-free but dot-prefixed home, and `.scripts`
is not an importable package. Loading it by path gives the tests the functions
rather than only the exit code, which is what lets them point the checker at a
crafted tree. One loader here, so no test file repeats the incantation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = REPO_ROOT / ".scripts" / "check_kit_layout.py"

_spec = importlib.util.spec_from_file_location("check_kit_layout", _SCRIPT)
if _spec is None or _spec.loader is None:  # pragma: no cover - a broken checkout
    raise ImportError(f"cannot load {_SCRIPT}")
_module = importlib.util.module_from_spec(_spec)
sys.modules["check_kit_layout"] = _module
_spec.loader.exec_module(_module)

check_all = _module.check_all
check_skills = _module.check_skills
check_flat_kind = _module.check_flat_kind
check_metadata = _module.check_metadata
read_frontmatter = _module.read_frontmatter
frontmatter_block = _module.frontmatter_block
main = _module.main
MAX_DEPTH = _module.MAX_DEPTH
