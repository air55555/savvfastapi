"""
Utility functions for the savvfastapi application.
"""
from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


# Regex pattern for cube directory names: cube_DD_MM_HH_MM_SS
FOLDER_RE = re.compile(r"^cube_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})$")


def get_free_disk_space(drive_letter: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """
    Get free disk space for a drive with timeout protection.
    Handles network drives (like S:) that may be disconnected.

    Args:
        drive_letter: Drive letter (e.g., 'C', 'D', 'S')
        timeout: Timeout in seconds for network operations

    Returns:
        Dict with space info or None on failure:
        {
            "free_gb": float,
            "total_gb": float,
            "used_percent": float,
            "available": bool,
            "error": str (optional, if available=False)
        }
    """
    try:
        if platform.system() == "Windows":
            path_str = f"{drive_letter}:\\"
        else:
            # On Linux, try to mount or use the path as-is
            path_str = f"/mnt/{drive_letter.lower()}" if drive_letter else "/"

        path = Path(path_str)

        # First check if path exists
        if not path.exists():
            return {
                "free_gb": None,
                "total_gb": None,
                "used_percent": None,
                "available": False,
                "error": "Drive does not exist",
            }

        # For network drive S:, use a more careful approach with connectivity check
        if drive_letter and drive_letter.upper() == "S":
            try:
                # Try to list directory contents to verify connectivity
                if platform.system() == "Windows":
                    result = subprocess.run(
                        ["dir", path_str],
                        capture_output=True,
                        timeout=timeout,
                        text=True,
                    )
                    if result.returncode != 0:
                        return {
                            "free_gb": None,
                            "total_gb": None,
                            "used_percent": None,
                            "available": False,
                            "error": "Drive not accessible",
                        }
                else:
                    # On Linux, try ls
                    result = subprocess.run(
                        ["ls", str(path)],
                        capture_output=True,
                        timeout=timeout,
                        text=True,
                    )
                    if result.returncode != 0:
                        return {
                            "free_gb": None,
                            "total_gb": None,
                            "used_percent": None,
                            "available": False,
                            "error": "Drive not accessible",
                        }
            except subprocess.TimeoutExpired:
                return {
                    "free_gb": None,
                    "total_gb": None,
                    "used_percent": None,
                    "available": False,
                    "error": "Timeout accessing drive",
                }
            except Exception:
                return {
                    "free_gb": None,
                    "total_gb": None,
                    "used_percent": None,
                    "available": False,
                    "error": "Error accessing drive",
                }

        # Get disk usage
        try:
            usage = shutil.disk_usage(str(path))
            total_gb = usage.total / (1024**3)
            free_gb = usage.free / (1024**3)
            used_percent = (usage.used / usage.total) * 100 if usage.total > 0 else 0

            return {
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_percent": round(used_percent, 1),
                "available": True,
            }
        except Exception as e:
            return {
                "free_gb": None,
                "total_gb": None,
                "used_percent": None,
                "available": False,
                "error": str(e),
            }
    except Exception as e:
        return {
            "free_gb": None,
            "total_gb": None,
            "used_percent": None,
            "available": False,
            "error": str(e),
        }


def get_dir_size(path: Path) -> int:
    """
    Get total size of directory in bytes.

    Args:
        path: Path to directory

    Returns:
        Total size in bytes, or 0 on error
    """
    try:
        return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())
    except Exception:
        return 0


def count_scanned_dirs(root_path: str, min_size_mb: int = 500) -> Dict[str, int]:
    """
    Count cube_* directories > min_size_mb, categorized by date.
    Analyzes timestamp from directory name pattern: cube_DD_MM_HH_MM_SS

    Args:
        root_path: Root directory path to scan for cube_* directories
        min_size_mb: Minimum directory size in MB to be counted (default: 500)

    Returns:
        Dict with counts:
        {
            "today": int,
            "this_week": int,
            "total": int
        }
    """
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    today_count = 0
    week_count = 0
    total_count = 0

    root = Path(root_path)
    if not root.exists():
        return {"today": today_count, "this_week": week_count, "total": total_count}

    for item in root.iterdir():
        if not item.is_dir() or not item.name.startswith("cube_"):
            continue

        m = FOLDER_RE.match(item.name)
        if not m:
            continue

        # Check size > min_size_mb
        size_mb = get_dir_size(item) / (1024**2)
        if size_mb <= min_size_mb:
            continue

        # Extract timestamp from folder name: cube_DD_MM_HH_MM_SS
        try:
            day, month, hour, minute, second = [int(x) for x in m.groups()]
            year = datetime.now().year
            folder_date = datetime(year, month, day, hour, minute, second).date()
        except (ValueError, IndexError):
            continue

        total_count += 1
        if folder_date == today:
            today_count += 1
        if folder_date >= week_start:
            week_count += 1

    return {"today": today_count, "this_week": week_count, "total": total_count}
