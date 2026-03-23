from __future__ import annotations

import argparse

from pipeline.acquire import run_acquire


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--form", default="10-K")
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()
    print(run_acquire(args.issuer, args.form, args.limit))


if __name__ == "__main__":
    main()
