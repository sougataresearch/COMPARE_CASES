"""Validation, environment checks, and run-directory helpers for continuous mode.

Deliberate duplicate of discreate_angle/utils.py, trimmed to what continuous
rotation actually needs: no angle-list parsing (continuous only takes two
fixed floats and a rotation ratio, asked directly in 01_main.py), and no
BMP-count disk estimate (continuous has no fixed image count decided ahead of
time — see continuous_engine.py for why).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Iterable

from config import DATA_ROOT, KINESIS_DIR, REQUIRED_KINESIS_DLLS


def optical_to_motor(optical_angle: float, offset: float) -> float:
    """motor_angle = (optical_angle + zero_offset) % 360. Same core formula
    as discreate_angle/utils.py; duplicated so this folder has no cross-import."""

    return (float(optical_angle) + float(offset)) % 360.0


def parse_ratio(text: str) -> tuple[int, int]:
    """Parse "slow:fast" revolution-ratio text (e.g. "1:5" -> PSA_QWP spins
    5x for every 1 revolution of PSG_QWP)."""

    slow, fast = (int(part.strip()) for part in text.split(":", 1))
    if slow <= 0 or fast <= 0:
        raise ValueError("Rotation ratio values must be positive integers.")
    return slow, fast


def create_run_directory(root: Path = DATA_ROOT) -> Path:
    """Create the next collision-free YYYY-MM-DD_RunXX directory tree.

    Same seven standard subfolders as discreate_angle for consistency, even
    though continuous mode's engine does not populate all of them yet.
    """

    root.mkdir(parents=True, exist_ok=True)
    prefix = date.today().isoformat()
    existing = [p for p in root.glob(f"{prefix}_Run*") if p.is_dir()]
    used = {int(p.name.rsplit("Run", 1)[1]) for p in existing if p.name.rsplit("Run", 1)[1].isdigit()}
    run_number = next(number for number in range(1, 10_000) if number not in used)
    run = root / f"{prefix}_Run{run_number:02d}"
    for child in ("Images", "Logs", "Config", "Reports", "Checkpoints"):
        (run / child).mkdir(parents=True, exist_ok=False)
    return run


def write_json(path: Path, payload: object) -> None:
    """Atomic JSON write: write to a ``.tmp`` sibling, then os.replace()."""

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def check_environment(output_root: Path = DATA_ROOT) -> list[tuple[str, bool, str]]:
    """Import/filesystem-only diagnostic checks, safe to run without hardware."""

    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0]))
    for package, import_name in (
        ("pythonnet", "clr"),
        ("IDS Peak", "ids_peak"),
        ("OpenCV", "cv2"),
        ("NumPy", "numpy"),
        ("Pandas", "pandas"),
    ):
        found = importlib.util.find_spec(import_name) is not None
        checks.append((package, found, "available" if found else "not importable"))
    checks.append(("Kinesis directory", KINESIS_DIR.is_dir(), str(KINESIS_DIR)))
    for dll in REQUIRED_KINESIS_DLLS:
        path = KINESIS_DIR / dll
        checks.append((dll, path.is_file(), str(path)))
    output_root.mkdir(parents=True, exist_ok=True)
    writable = os.access(output_root, os.W_OK)
    checks.append(("Data directory writable", writable, str(output_root.resolve())))
    free_gb = shutil.disk_usage(output_root).free / 1024**3
    checks.append(("Free disk >= 1 GB", free_gb >= 1.0, f"{free_gb:.2f} GB"))
    return checks


def yes_no(prompt: str, default: bool = False) -> bool:
    """Ask a Y/n question; blank input accepts ``default``."""

    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = input(prompt + suffix).strip().lower()
    return default if not answer else answer in {"y", "yes"}


def print_angles(label: str, optical: Iterable[float], offset: float) -> None:
    """Print an angle list next to its motor-angle equivalent."""

    optical_list = list(optical)
    motor_list = [optical_to_motor(value, offset) for value in optical_list]
    print(f"{label} optical angles: {optical_list}")
    print(f"{label} motor angles:   {motor_list}")
