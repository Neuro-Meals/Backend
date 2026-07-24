"""
Central SQLAlchemy model loader.

Alembic imports this module before inspecting Base.metadata.
Importing every module that contains SQLAlchemy models registers all tables
with app.db.database.Base.
"""

from __future__ import annotations
from app.modules.users import rbac_models as rbac_models
import importlib
import importlib.util
import pkgutil
import app.modules
from app.db.database import Base



def import_all_model_modules() -> list[str]:
    """
    Import every app.modules.<module>.models module that exists.

    This avoids maintaining duplicate model-import lists in Alembic's env.py.
    It only imports modules named `models.py` inside app/modules packages.
    """

    imported_modules: list[str] = []

    for module_info in pkgutil.iter_modules(
        app.modules.__path__,
        prefix="app.modules.",
    ):
        package_name = module_info.name
        model_module_name = f"{package_name}.models"

        try:
            model_spec = importlib.util.find_spec(model_module_name)
        except (ImportError, AttributeError, ModuleNotFoundError):
            model_spec = None

        if model_spec is None:
            continue

        # Do not suppress errors raised inside a real models module.
        # Those errors must be fixed rather than silently ignored.
        importlib.import_module(model_module_name)
        imported_modules.append(model_module_name)

    return sorted(imported_modules)

IMPORTED_MODEL_MODULES = import_all_model_modules()

__all__ = [
    "Base",
    "IMPORTED_MODEL_MODULES",
    "import_all_model_modules",
]