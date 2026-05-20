"""Ensure repo root on cwd/sys.path before importing ``app`` (optional)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent


def ensure_repo_working_directory() -> Path:
    """Set cwd to typical_infrastructure root when launched from elsewhere."""
    root = _REPO_ROOT
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.chdir(root)
    return root


def ensure_typical_infra_working_directory() -> Path:
    """Alias for symmetry with ``skill_assessment.bootstrap``."""
    infra = os.getenv("TYPICAL_INFRA_ROOT", "").strip()
    if infra:
        p = Path(infra).resolve()
        if p.is_dir():
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
            os.chdir(p)
            return p
    return ensure_repo_working_directory()
