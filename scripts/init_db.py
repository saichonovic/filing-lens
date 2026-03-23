from __future__ import annotations

from app.db import create_all_tables


def main() -> None:
    create_all_tables()
    print("Created FilingLens tables from SQLAlchemy metadata.")


if __name__ == "__main__":
    main()
