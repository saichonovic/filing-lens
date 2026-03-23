from __future__ import annotations

import argparse

from pipeline.derive import run_derive, run_derive_by_ticker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer-id")
    parser.add_argument("--ticker")
    parser.add_argument("--signals")
    parser.add_argument("--with-docetl", action="store_true")
    args = parser.parse_args()
    signal_filter = args.signals.split(",") if args.signals else None
    if args.ticker:
        print(run_derive_by_ticker(args.ticker, signal_filter=signal_filter, use_docetl=args.with_docetl))
        return
    if not args.issuer_id:
        parser.error("--issuer-id is required unless --ticker is set.")
    print(run_derive(args.issuer_id, signal_filter=signal_filter, use_docetl=args.with_docetl))


if __name__ == "__main__":
    main()
