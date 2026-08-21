"""Loading this repository's dependency-free logic without its dependency stack.

``app/services/scoring_service.py`` and ``app/models/enums.py`` import nothing
outside the standard library. They are nonetheless unreachable through a normal
``import app.services.scoring_service``, because ``app/models/__init__.py``
eagerly imports every ORM model, which pulls in SQLAlchemy, asyncpg and the whole
database layer.

For the product that is the right trade — one import and the ORM is ready. For
ZERO it is the wrong one: scoring a list of candidates would require Postgres
drivers to be installed and several tens of megabytes to be resident on a laptop
that is also running an LLM. So the two pure modules are loaded directly from
their files, bypassing the package ``__init__``.

The bypass is verified, not assumed: ``load_scoring`` fails loudly if the module
it loaded is not the one it expected, so a future refactor that gives these
modules real dependencies breaks here rather than silently loading something else.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

#: Repository root — this file is at <root>/zero_agent/pure.py.
REPO_ROOT = Path(__file__).resolve().parent.parent

PURE_MODULES: dict[str, Path] = {
    "app.models.enums": REPO_ROOT / "app" / "models" / "enums.py",
    "app.services.scoring_service": REPO_ROOT / "app" / "services" / "scoring_service.py",
}


class PureImportError(ImportError):
    """A module that should have been dependency-free could not be loaded."""


def _load_module(name: str, path: Path) -> ModuleType:
    """Load one file as ``name`` without importing its parent packages."""
    if name in sys.modules:
        return sys.modules[name]
    if not path.is_file():
        raise PureImportError(f"{name}: {path} does not exist")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PureImportError(f"{name}: no import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so a module that refers to itself resolves,
    # and so a second call reuses this instance rather than loading a twin whose
    # enum members would not compare equal to the first one's.
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        raise PureImportError(f"{name} is no longer dependency-free: {exc}") from exc
    return module


def load_scoring() -> tuple[ModuleType, ModuleType]:
    """Return ``(enums, scoring_service)``, loaded without the database layer."""
    enums = _load_module("app.models.enums", PURE_MODULES["app.models.enums"])
    for required in ("LeadType", "CompanyStatus", "LeadPriority"):
        if not hasattr(enums, required):
            raise PureImportError(f"app.models.enums is missing {required}")

    scoring = _load_module(
        "app.services.scoring_service", PURE_MODULES["app.services.scoring_service"]
    )
    for required in ("ScoreInput", "calculate_score"):
        if not hasattr(scoring, required):
            raise PureImportError(f"app.services.scoring_service is missing {required}")
    return enums, scoring


__all__ = ["PURE_MODULES", "REPO_ROOT", "PureImportError", "load_scoring"]
