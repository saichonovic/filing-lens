from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db import get_session
from models.tables import Filing, FilingSection, Issuer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--fiscal-year", type=int)
    args = parser.parse_args()

    with get_session() as session:
        issuer = session.scalar(select(Issuer).where(Issuer.ticker == args.ticker))
        if issuer is None:
            raise SystemExit(f"Issuer {args.ticker} not found.")

        filings = session.scalars(
            select(Filing)
            .where(Filing.issuer_id == issuer.id, Filing.form_type == "10-K")
            .order_by(Filing.period_end_date.desc(), Filing.filing_date.desc())
        ).all()

        for filing in filings:
            if args.fiscal_year and filing.fiscal_year != args.fiscal_year:
                continue

            print("\n" + "=" * 60)
            print(f"{filing.form_type} {filing.fiscal_year} ({filing.accession_number})")
            print("=" * 60)

            sections = session.scalars(
                select(FilingSection)
                .where(FilingSection.filing_id == filing.id, FilingSection.section_code == "FOOTNOTE_DEBT")
                .order_by(FilingSection.section_order)
            ).all()

            if not sections:
                print("  [NO FOOTNOTE_DEBT SECTION FOUND]")
                print("  -> check section_parser footnote patterns")
                continue

            for section in sections:
                print(f"\n  Section: {section.section_title}")
                print(f"  Length: {len(section.section_text or '')} chars")
                print(f"  Confidence: {section.confidence}")
                print("\n  --- TEXT (first 3000 chars) ---")
                print((section.section_text or "")[:3000])
                print("\n  --- TEXT (3000-5000 chars) ---")
                print((section.section_text or "")[3000:5000])


if __name__ == "__main__":
    main()
