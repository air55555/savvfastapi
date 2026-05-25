"""
Move directories from a local source to a network (or other) destination.

For each matched directory:
  1. Log start to screen + palletes_scan (size, per-extension file counts).
  2. Copy tree to destination.
  3. Verify destination matches source; if OK, delete source directory.
  4. Log result to screen + palletes_scan.

Msg values use prefix ``dir_move:`` for easy filtering in SQL.
"""
from __future__ import annotations

import argparse
import fnmatch
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
from db import init_db, insert_palletes_scan  # noqa: E402

MSG_PREFIX = "dir_move"
DEFAULT_ID_POINT = "dir_move"


@dataclass(frozen=True)
class DirStats:
    size_bytes: int
    total_files: int
    by_ext: dict[str, int]

    def format_msg(self) -> str:
        ext_parts = ",".join(
            f"{ext}:{count}" for ext, count in sorted(self.by_ext.items())
        )
        return (
            f"size_bytes={self.size_bytes}; total_files={self.total_files}; "
            f"by_ext={ext_parts or '(none)'}"
        )

    def format_compare(self, other: DirStats, label: str) -> str:
        return f"{label}: {self.format_msg()}"


def summarize_dir(path: Path) -> DirStats:
    size_bytes = 0
    by_ext: Counter[str] = Counter()
    total_files = 0

    for entry in path.rglob("*"):
        if not entry.is_file():
            continue
        total_files += 1
        size_bytes += entry.stat().st_size
        ext = entry.suffix.lower() if entry.suffix else "(no_ext)"
        by_ext[ext] += 1

    return DirStats(size_bytes=size_bytes, total_files=total_files, by_ext=dict(by_ext))


def stats_match(src: DirStats, dst: DirStats) -> tuple[bool, str]:
    if src.size_bytes != dst.size_bytes:
        return False, f"size_bytes mismatch src={src.size_bytes} dst={dst.size_bytes}"
    if src.total_files != dst.total_files:
        return False, f"total_files mismatch src={src.total_files} dst={dst.total_files}"
    all_exts = sorted(set(src.by_ext) | set(dst.by_ext))
    for ext in all_exts:
        s = src.by_ext.get(ext, 0)
        d = dst.by_ext.get(ext, 0)
        if s != d:
            return False, f"ext {ext} mismatch src={s} dst={d}"
    return True, "size and file counts match"


def match_dir_name(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def find_matching_dirs(source: Path, patterns: list[str]) -> list[Path]:
    dirs = [
        p
        for p in sorted(source.iterdir())
        if p.is_dir() and match_dir_name(p.name, patterns)
    ]
    return dirs


def log(msg: str) -> None:
    print(msg, flush=True)


def insert_start_record(
    id_point: str,
    dir_name: str,
    src: Path,
    dst: Path,
    stats: DirStats,
) -> None:
    insert_palletes_scan(
        id_point,
        dir_name,
        dir_name,
        "Copying",
        "Started",
        f"{MSG_PREFIX}:start; source={src}; dest={dst}; {stats.format_msg()}",
    )


def insert_result_record(
    id_point: str,
    dir_name: str,
    src: Path,
    dst: Path,
    src_stats: DirStats,
    dst_stats: DirStats | None,
    ok: bool,
    note: str,
    deleted: bool,
) -> None:
    if dst_stats is not None:
        compare = (
            f"{src_stats.format_compare(dst_stats, 'src')}; "
            f"{dst_stats.format_compare(src_stats, 'dst')}; {note}"
        )
    else:
        compare = f"{src_stats.format_msg()}; {note}"
    details = f"{dir_name}; deleted_source={deleted}; {compare}"
    insert_palletes_scan(
        id_point,
        dir_name,
        details,
        "Moved" if ok and deleted else "Copy",
        "Ok" if ok else "Fail",
        f"{MSG_PREFIX}:result; source={src}; dest={dst}; {note}",
    )


def move_one_dir(
    src_dir: Path,
    dest_root: Path,
    id_point: str,
    overwrite: bool,
    dry_run: bool,
) -> tuple[bool, str]:
    dir_name = src_dir.name
    dst_dir = dest_root / dir_name

    log(f"--- {dir_name} ---")
    src_stats = summarize_dir(src_dir)
    log(f"[start] {src_stats.format_msg()}")

    if dst_dir.exists() and not overwrite:
        note = f"destination already exists: {dst_dir}"
        log(f"[skip] {note}")
        if not dry_run:
            insert_result_record(
                id_point, dir_name, src_dir, dst_dir, src_stats, None, False, note, False
            )
        return False, note

    if dry_run:
        log(f"[dry-run] would copy {src_dir} -> {dst_dir}")
        log(f"[dry-run] would verify and delete source if match")
        return True, "dry-run"

    insert_start_record(id_point, dir_name, src_dir, dst_dir, src_stats)

    log(f"[copy] {src_dir} -> {dst_dir}")
    try:
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=overwrite)
    except Exception as exc:
        note = f"copy failed: {exc}"
        log(f"[error] {note}")
        insert_result_record(
            id_point, dir_name, src_dir, dst_dir, src_stats, None, False, note, False
        )
        return False, note

    log("[verify] comparing source and destination")
    dst_stats = summarize_dir(dst_dir)
    log(f"[verify] dst {dst_stats.format_msg()}")

    ok, note = stats_match(src_stats, dst_stats)
    deleted = False
    if ok:
        log(f"[verify] OK — {note}")
        log(f"[delete] removing source {src_dir}")
        shutil.rmtree(src_dir)
        deleted = True
        log("[done] source removed")
    else:
        log(f"[verify] FAIL — {note}; source kept")

    insert_result_record(
        id_point, dir_name, src_dir, dst_dir, src_stats, dst_stats, ok, note, deleted
    )
    return ok and deleted, note


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy directories matching wildcards from source to destination, "
            "log progress to screen and palletes_scan, verify, then delete source on match."
        )
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Root directory containing folders to move (e.g. D:\\HSM_CAPTURE).",
    )
    parser.add_argument(
        "--dest",
        required=True,
        type=Path,
        help="Destination root on network drive (e.g. \\\\server\\share\\HSM_CAPTURE).",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        dest="patterns",
        metavar="GLOB",
        help="Directory name wildcard, repeatable (e.g. --pattern 'cube_*').",
    )
    parser.add_argument(
        "--id-point",
        default=DEFAULT_ID_POINT,
        help=f"IDPoint value for palletes_scan rows (default: {DEFAULT_ID_POINT}).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace destination directory if it already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions only; do not copy, delete, or write to DB.",
    )
    args = parser.parse_args()

    patterns = args.patterns or ["*"]
    source = args.source.resolve()
    dest = args.dest

    if not source.is_dir():
        log(f"Source not found or not a directory: {source}")
        return 1

    if not args.dry_run:
        init_db()
        log(f"Using DB: {db.DB_PATH}")

    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    elif not dest.exists():
        log(f"[dry-run] destination would be created: {dest}")

    dirs = find_matching_dirs(source, patterns)
    if not dirs:
        log(f"No directories matching {patterns!r} under {source}")
        return 0

    log(f"Found {len(dirs)} director{'y' if len(dirs) == 1 else 'ies'}: {[d.name for d in dirs]}")
    log(f"Source: {source}")
    log(f"Dest:   {dest}")
    log(f"Patterns: {patterns}")

    ok_count = 0
    fail_count = 0
    for src_dir in dirs:
        ok, _ = move_one_dir(
            src_dir=src_dir,
            dest_root=dest,
            id_point=args.id_point,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
        if ok:
            ok_count += 1
        else:
            fail_count += 1

    log(f"Finished: ok={ok_count} failed/skipped={fail_count} total={len(dirs)}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
