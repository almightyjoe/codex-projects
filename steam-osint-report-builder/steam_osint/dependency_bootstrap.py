from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REQUIRED_IMPORTS = {
    "requests": "requests",
    "bs4": "beautifulsoup4",
}

OPTIONAL_IMPORTS = {
    "networkx": "networkx",
    "matplotlib": "matplotlib",
}


def ensure_requirements() -> None:
    missing = _missing_packages({**REQUIRED_IMPORTS, **OPTIONAL_IMPORTS})
    if not missing:
        return
    requirements = Path(__file__).resolve().parent.parent / "requirements.txt"
    if not requirements.exists():
        _show_bootstrap_error(f"Missing requirements file: {requirements}")
        raise SystemExit(1)

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
    except Exception as exc:
        names = ", ".join(sorted(set(missing)))
        _show_bootstrap_error(
            "Could not install required Python packages.\n\n"
            f"Missing: {names}\n"
            f"Requirements: {requirements}\n\n"
            f"Error: {exc}"
        )
        raise SystemExit(1)

    still_missing = _missing_packages(REQUIRED_IMPORTS)
    if still_missing:
        _show_bootstrap_error(f"Required packages are still missing after install: {', '.join(still_missing)}")
        raise SystemExit(1)


def _missing_packages(import_to_package: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for import_name, package_name in import_to_package.items():
        if importlib.util.find_spec(import_name) is None:
            missing.append(package_name)
    return missing


def _show_bootstrap_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Steam OSINT Report Builder Setup", message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)
