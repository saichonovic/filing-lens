from __future__ import annotations

import argparse

from pipeline.extract import run_extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filing-id", required=True)
    args = parser.parse_args()
    print(run_extract(args.filing_id))


if __name__ == "__main__":
    main()
