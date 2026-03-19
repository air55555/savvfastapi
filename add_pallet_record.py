import argparse
import sys
from typing import List

from db import init_db, insert_palletes_scan


def main(argv: List[str]) -> int:
	parser = argparse.ArgumentParser(description="Insert one record into 'palletes_scan' table")
	parser.add_argument("--sscc", default="148102689000000010", help="SSCC value (default: 148102689000000010)")
	parser.add_argument("--idpoint", default="ID1", help="IDPoint value (default: ID1)")
	parser.add_argument("--details", default="manual insert", help="Details value (default: manual insert)")
	parser.add_argument("--status", default="Scanned", help="Status value (default: Scanned)")
	parser.add_argument("--result", default="Ok", help="Result value (default: Ok)")
	parser.add_argument("--msg", default="done", help="Msg value (default: done)")
	args = parser.parse_args(argv)

	# Ensure tables exist
	init_db()

	insert_palletes_scan(args.idpoint, args.sscc, args.details, args.status, args.result, args.msg)
	print(
		"Inserted into palletes_scan "
		f"(IDPoint={args.idpoint}, SSCC={args.sscc}, Details={args.details}, "
		f"Status={args.status}, Result={args.result}, Msg={args.msg})"
	)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))


