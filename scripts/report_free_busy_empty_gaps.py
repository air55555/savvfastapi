"""
Report empty windows: free -> next busy with no set_pallet_requests rows in between.
Writes CSV (default: free_busy_empty_gaps.csv in project root).
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "savvfastapi.db"
DEFAULT_CSV = Path(__file__).resolve().parents[1] / "free_busy_empty_gaps.csv"


def find_empty_gaps(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, SSCC, IDPoint, Message, Weight, created_at
        FROM set_pallet_requests
        ORDER BY id
        """
    ).fetchall()

    gaps: list[dict] = []
    for i, r in enumerate(rows):
        if r[2] != "free":  # IDPoint
            continue
        for j in range(i + 1, len(rows)):
            nxt = rows[j]
            if nxt[2] != "busy":
                continue
            between = rows[i + 1 : j]
            t0 = datetime.fromisoformat(r[5])
            t1 = datetime.fromisoformat(nxt[5])
            gap_seconds = (t1 - t0).total_seconds()
            gaps.append(
                {
                    "free_id": r[0],
                    "free_at": r[5],
                    "free_sscc": r[1],
                    "busy_id": nxt[0],
                    "busy_at": nxt[5],
                    "busy_sscc": nxt[1],
                    "between_count": len(between),
                    "between_ids": ";".join(str(x[0]) for x in between),
                    "gap_seconds": int(gap_seconds),
                    "gap_minutes": round(gap_seconds / 60, 2),
                }
            )
            break
    return gaps


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "free_id",
        "free_at",
        "free_sscc",
        "busy_id",
        "busy_at",
        "busy_sscc",
        "between_count",
        "between_ids",
        "gap_seconds",
        "gap_minutes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CSV report of free->busy gaps with no intervening set_pallet_requests rows."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_CSV, help="Output CSV path")
    parser.add_argument(
        "--min-minutes",
        type=float,
        default=0,
        help="Only include gaps at least this many minutes (default: 0 = all empty gaps)",
    )
    parser.add_argument(
        "--all-pairs",
        action="store_true",
        help="Include non-empty gaps too (between_count > 0)",
    )
    args = parser.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"Database not found: {args.db}")

    conn = sqlite3.connect(args.db)
    try:
        gaps = find_empty_gaps(conn)
    finally:
        conn.close()

    if not args.all_pairs:
        gaps = [g for g in gaps if g["between_count"] == 0]
    if args.min_minutes > 0:
        gaps = [g for g in gaps if g["gap_minutes"] >= args.min_minutes]

    gaps.sort(key=lambda g: g["free_id"], reverse=True)
    write_csv(args.output, gaps)
    print(f"Wrote {len(gaps)} rows to {args.output}")


if __name__ == "__main__":
    main()
