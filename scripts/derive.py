from __future__ import annotations

import argparse

from pipeline.derive import run_derive


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer-id", required=True)
    parser.add_argument("--signals", default="all")
    args = parser.parse_args()
    print(run_derive(args.issuer_id, args.signals))


if __name__ == "__main__":
    main()
