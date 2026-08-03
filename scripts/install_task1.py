#!/usr/bin/env python3
"""Install Phase 1 Task 1 into a NeuroMeals backend checkout."""
from pathlib import Path
import shutil
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()

required = [TARGET_ROOT / "app" / "main.py", TARGET_ROOT / "migrations" / "versions"]
if not all(path.exists() for path in required):
    raise SystemExit(f"Target does not look like the NeuroMeals backend: {TARGET_ROOT}")

for relative in [
    Path("app/modules/health_profile_options"),
    Path("migrations/versions/8f3d1a7c9b20_add_health_profile_options.py"),
]:
    source = PACKAGE_ROOT / relative
    target = TARGET_ROOT / relative
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.is_file():
                shutil.copy2(item, target / item.name)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

main_path = TARGET_ROOT / "app/main.py"
main_text = main_path.read_text(encoding="utf-8")
import_line = "from app.modules.health_profile_options.router import router as health_profile_options_router\n"
include_line = "app.include_router(health_profile_options_router)\n"

if import_line not in main_text:
    anchor = "from app.modules.customer_drivers.router import router as customer_driver_router\n"
    if anchor not in main_text:
        raise SystemExit("Could not find main.py import anchor. Add the router manually using README.md.")
    main_text = main_text.replace(anchor, anchor + import_line, 1)

if include_line not in main_text:
    anchor = "app.include_router(customer_driver_router)\n"
    if anchor not in main_text:
        raise SystemExit("Could not find main.py include anchor. Add the router manually using README.md.")
    main_text = main_text.replace(anchor, anchor + include_line, 1)

main_path.write_text(main_text, encoding="utf-8")
print(f"Task 1 installed into: {TARGET_ROOT}")
print("Next: alembic upgrade head")
