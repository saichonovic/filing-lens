from __future__ import annotations

import argparse

from pipeline.resolve import run_resolve, run_resolve_by_ticker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer-id")
    parser.add_argument("--ticker")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.ticker:
        print(run_resolve_by_ticker(args.ticker, force=args.force))
        return
    if not args.issuer_id:
        parser.error("--issuer-id is required unless --ticker is set.")
    print(run_resolve(args.issuer_id, force=args.force))


if __name__ == "__main__":
    main()
