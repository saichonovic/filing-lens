from __future__ import annotations

import argparse

from pipeline.extract import run_extract, run_extract_all_pending


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filing-id")
    parser.add_argument("--all-pending", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.all_pending:
        print(run_extract_all_pending(force=args.force))
        return
    if not args.filing_id:
        parser.error("--filing-id is required unless --all-pending is set.")
    print(run_extract(args.filing_id, force=args.force))


if __name__ == "__main__":
    main()
