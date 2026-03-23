from __future__ import annotations

import argparse

from pipeline.publish import run_publish


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer-id", required=True)
    args = parser.parse_args()
    print(run_publish(args.issuer_id))


if __name__ == "__main__":
    main()
