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
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

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


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def collect_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def summarize_files(
    files: list[Path],
    *,
    label: str,
    progress_every: int,
    on_progress: Callable[[str], None] | None = None,
) -> DirStats:
    size_bytes = 0
    by_ext: Counter[str] = Counter()
    total = len(files)
    last_pct = -1

    for idx, entry in enumerate(files, start=1):
        file_size = entry.stat().st_size
        size_bytes += file_size
        ext = entry.suffix.lower() if entry.suffix else "(no_ext)"
        by_ext[ext] += 1

        pct = (idx * 100) // total if total else 100
        report = (
            idx == 1
            or idx == total
            or idx % progress_every == 0
            or pct >= last_pct + 5
        )
        if report and on_progress is not None:
            last_pct = pct
            on_progress(
                f"[{label}] {idx}/{total} files ({pct}%), "
                f"{format_bytes(size_bytes)} scanned"
            )

    return DirStats(size_bytes=size_bytes, total_files=total, by_ext=dict(by_ext))


def summarize_dir(
    path: Path,
    *,
    label: str = "scan",
    progress_every: int = 10,
    on_progress: Callable[[str], None] | None = None,
) -> DirStats:
    files = collect_files(path)
    if on_progress is not None:
        on_progress(f"[{label}] found {len(files)} files under {path.name}")
    return summarize_files(
        files, label=label, progress_every=progress_every, on_progress=on_progress
    )


def copy_dir_with_progress(
    src_dir: Path,
    dst_dir: Path,
    files: list[Path],
    *,
    progress_every: int,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    total = len(files)
    copied_bytes = 0
    last_pct = -1
    t0 = time.monotonic()

    for idx, src_file in enumerate(files, start=1):
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied_bytes += src_file.stat().st_size

        pct = (idx * 100) // total if total else 100
        report = (
            idx == 1
            or idx == total
            or idx % progress_every == 0
            or pct >= last_pct + 5
        )
        if report and on_progress is not None:
            last_pct = pct
            elapsed = time.monotonic() - t0
            rate = copied_bytes / elapsed if elapsed > 0 else 0
            on_progress(
                f"[copy] {idx}/{total} files ({pct}%), "
                f"{format_bytes(copied_bytes)} copied, "
                f"{format_bytes(int(rate))}/s"
            )

    return copied_bytes


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
    *,
    dir_index: int,
    dir_total: int,
    progress_every: int,
) -> tuple[bool, str]:
    dir_name = src_dir.name
    dst_dir = dest_root / dir_name

    log(f"--- [{dir_index}/{dir_total}] {dir_name} ---")
    log("[scan] scanning source...")
    src_stats = summarize_dir(
        src_dir, label="scan", progress_every=progress_every, on_progress=log
    )
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
        log(
            f"[dry-run] {src_stats.total_files} files, "
            f"{format_bytes(src_stats.size_bytes)}"
        )
        log("[dry-run] would verify and delete source if match")
        return True, "dry-run"

    insert_start_record(id_point, dir_name, src_dir, dst_dir, src_stats)

    files = collect_files(src_dir)
    if overwrite and dst_dir.exists():
        log(f"[copy] removing existing destination {dst_dir}")
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    log(f"[copy] {src_dir} -> {dst_dir} ({src_stats.total_files} files)")
    try:
        copy_dir_with_progress(
            src_dir,
            dst_dir,
            files,
            progress_every=progress_every,
            on_progress=log,
        )
        log(f"[copy] done — {format_bytes(src_stats.size_bytes)}")
    except Exception as exc:
        note = f"copy failed: {exc}"
        log(f"[error] {note}")
        insert_result_record(
            id_point, dir_name, src_dir, dst_dir, src_stats, None, False, note, False
        )
        return False, note

    log("[verify] scanning destination...")
    dst_stats = summarize_dir(
        dst_dir, label="verify", progress_every=progress_every, on_progress=log
    )
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
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        metavar="N",
        help="Log copy/scan progress every N files (also at 5%% steps). Default: 10.",
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
    dir_total = len(dirs)
    progress_every = max(1, args.progress_every)
    for dir_index, src_dir in enumerate(dirs, start=1):
        ok, _ = move_one_dir(
            src_dir=src_dir,
            dest_root=dest,
            id_point=args.id_point,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            dir_index=dir_index,
            dir_total=dir_total,
            progress_every=progress_every,
        )
        if ok:
            ok_count += 1
        else:
            fail_count += 1

    log(f"Finished: ok={ok_count} failed/skipped={fail_count} total={len(dirs)}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
