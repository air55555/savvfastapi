from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from db import (  # noqa: E402
	init_db,
	insert_get_camera_res_request,
	insert_get_camera_res_response,
	insert_log,
	insert_palletes_scan,
	insert_set_pallet_request,
	insert_set_pallet_response,
)


def main() -> int:
	parser = argparse.ArgumentParser(description="Seed ALL tables with test data (standalone).")
	parser.add_argument("--n", type=int, default=25, help="Number of random rows per table (default: 25)")
	args = parser.parse_args()

	init_db()

	id_points = ["ID1", "ID2", "ID3"]
	ssccs = ["111", "666", "777", "148102689000000010", "00312345000000000123"]
	user_agents = ["curl/8.0", "python-requests/2.x", "PostmanRuntime/7.x"]

	for i in range(args.n):
		sscc = random.choice(ssccs)
		idp = random.choice(id_points)
		insert_set_pallet_request(sscc, idp, "PalletOnID", float(random.randint(1, 200)))
		insert_set_pallet_response(sscc, "Ok")

		insert_palletes_scan(
			idp,
			sscc,
			f"seed all tables #{i+1}",
			random.choice(["Scanned", "Rejected", "Accepted"]),
			random.choice(["Ok", "BadLabel", "Damaged", "NotFound"]),
			random.choice(["done", "needs review", "auto reject", "ok"]),
		)

		insert_get_camera_res_request(sscc)
		insert_get_camera_res_response(
			idp,
			sscc,
			"PalletResult",
			str(random.randint(0, 100)),
			str(random.randint(0, 10)),
			random.choice(["Ok", "BadLabel", "Damaged", "NotFound"]),
		)

		insert_log(
			method="POST",
			path=random.choice(["/api/setpallet", "/api/getcamerares"]),
			status_code=200,
			duration_ms=float(random.randint(1, 2000)),
			client_ip="127.0.0.1",
			user_agent=random.choice(user_agents),
		)

	print("Seeded all tables with test data.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

