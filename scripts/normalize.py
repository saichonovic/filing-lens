from __future__ import annotations

import argparse

from pipeline.normalize import run_normalize, run_normalize_all_extracted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filing-id")
    parser.add_argument("--all-extracted", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.all_extracted:
        print(run_normalize_all_extracted(force=args.force))
        return
    if not args.filing_id:
        parser.error("--filing-id is required unless --all-extracted is set.")
    print(run_normalize(args.filing_id, force=args.force))


if __name__ == "__main__":
    main()
