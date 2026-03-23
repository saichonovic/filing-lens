from __future__ import annotations

import argparse

from pipeline.publish import run_publish, run_publish_by_ticker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer-id")
    parser.add_argument("--ticker")
    parser.add_argument("--no-print", action="store_true")
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--alerts-only", action="store_true")
    args = parser.parse_args()
    if args.ticker:
        print(
            run_publish_by_ticker(
                args.ticker,
                output_json=not args.no_export,
                print_report=not args.no_print and not args.alerts_only,
                print_alerts=True,
            )
        )
        return
    if not args.issuer_id:
        parser.error("--issuer-id is required unless --ticker is set.")
    print(
        run_publish(
            args.issuer_id,
            output_json=not args.no_export,
            print_report=not args.no_print and not args.alerts_only,
            print_alerts=True,
        )
    )


if __name__ == "__main__":
    main()
