"""
Export all discovered leads from the lead scraper DB to leads.csv.
Run: python export_leads.py
"""

import asyncio
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "Autonomous-Website-Lead-Scraper"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "Autonomous-Website-Lead-Scraper/.env")

from sqlalchemy import select, outerjoin
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.company import Company
from app.models.contact import Contact

OUT = Path(__file__).parent / "data" / "leads.csv"
FIELDS = ["lead_id", "company", "email", "website", "contact_name", "role", "state", "last_sent_at"]


async def export():
    db_url = os.getenv("DATABASE_URL", "")
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # Fetch companies with their first contact (if any)
        result = await db.execute(select(Company).order_by(Company.id))
        companies = result.scalars().all()

        # Fetch contacts keyed by company_id
        c_result = await db.execute(select(Contact).order_by(Contact.id))
        contacts_raw = c_result.scalars().all()

    contacts_by_company: dict[int, Contact] = {}
    for c in contacts_raw:
        if c.company_id not in contacts_by_company:
            contacts_by_company[c.company_id] = c

    rows = []
    for company in companies:
        contact = contacts_by_company.get(company.id)
        rows.append({
            "lead_id": company.id,
            "company": company.name or "",
            "email": (contact.email if contact else "") or "",
            "website": company.website or "",
            "contact_name": (contact.full_name if contact else "") or "",
            "role": (contact.role if contact else "") or "",
            "state": "NEW",
            "last_sent_at": "",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    await engine.dispose()
    print(f"Exported {len(rows)} leads → {OUT}")


asyncio.run(export())
