import argparse
import sys
from typing import List

from db import init_db, get_connection


def insert_into_palletes(sscc: str, status: str) -> int:
	conn = get_connection()
	try:
		cur = conn.execute(
			"""
			INSERT INTO palletes_scan(SSCC, Status)
			VALUES(?, ?)
			""",
			(sscc, status),
		)
		conn.commit()
		return cur.lastrowid
	finally:
		conn.close()


def main(argv: List[str]) -> int:
	parser = argparse.ArgumentParser(description="Insert one record into 'palletes_scan' table")
	parser.add_argument("--sscc", default="148102689000000010", help="SSCC value (default: 148102689000000010)")
	parser.add_argument("--status", default="Ok", help="Status value (default: Ok)")
	args = parser.parse_args(argv)

	# Ensure tables exist
	init_db()

	row_id = insert_into_palletes(args.sscc, args.status)
	print(f"Inserted into palletes_scan with id={row_id}, SSCC={args.sscc}, Status={args.status}")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))


