from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1]))

from db import init_db, insert_palletes_scan


def _make_rows(n: int) -> List[Tuple[str, str, str, str, str, str]]:
	id_points = ["ID1", "ID2", "ID3"]
	ssccs = [
		"111",
		"666",
		"777",
		"00312345000000000123",
		"00312345000000000456",
		"00312345000000000789",
	]
	statuses = ["Scanned", "Rejected", "Accepted"]
	results = ["Ok", "BadLabel", "Damaged", "NotFound"]
	msgs = ["done", "needs review", "auto reject", "ok"]

	rows: List[Tuple[str, str, str, str, str, str]] = []
	for i in range(n):
		id_point = random.choice(id_points)
		sscc = random.choice(ssccs)
		status = random.choice(statuses)
		result = random.choice(results)
		msg = random.choice(msgs)
		details = f"test record #{i+1} ({status}/{result})"
		rows.append((id_point, sscc, details, status, result, msg))

	# Ensure canonical examples exist for README flows
	rows.extend(
		[
			("ID1", "111", "good scan result", "Accepted", "Ok", "done"),
			("ID2", "666", "failed quality check", "Rejected", "BadLabel", "auto reject"),
			("ID3", "777", "unscanned pallet", "Scanned", "NotFound", "needs review"),
		]
	)
	return rows


def main() -> int:
	parser = argparse.ArgumentParser(description="Seed palletes_scan with test records (standalone).")
	parser.add_argument("--n", type=int, default=20, help="Number of random rows to insert (default: 20)")
	args = parser.parse_args()

	init_db()
	for row in _make_rows(args.n):
		insert_palletes_scan(*row)

	print("Seeded palletes_scan with test records.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

