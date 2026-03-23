from __future__ import annotations

import argparse

from pipeline.resolve import run_resolve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer-id", required=True)
    args = parser.parse_args()
    print(run_resolve(args.issuer_id))


if __name__ == "__main__":
    main()
