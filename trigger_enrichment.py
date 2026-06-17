"""
Trigger crawl → analyse chain for all companies that have a website.
Run from the project root with the venv active.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from celery import chain
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.company import Company
from app.workers.tasks import analyse_website_task, crawl_company_task


async def get_companies():
    db_url = os.getenv("DATABASE_URL", "")
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        result = await db.execute(select(Company).order_by(Company.id))
        companies = result.scalars().all()
        data = [(c.id, c.name, c.website) for c in companies]
    await engine.dispose()
    return data


def main():
    companies = asyncio.run(get_companies())
    crawl_count = 0
    skip_count = 0
    for company_id, name, website in companies:
        if website:
            # Chain: crawl first, then analyse once crawl completes
            chain(
                crawl_company_task.si(company_id),
                analyse_website_task.si(company_id),
            ).delay()
            print(f"  queued crawl→analyse → [{company_id}] {name}")
            crawl_count += 1
        else:
            print(f"  skip (no website)    → [{company_id}] {name}")
            skip_count += 1

    print(f"\nQueued {crawl_count} crawl+analyse chains, skipped {skip_count} (no website).")
    print("Watch progress: sudo journalctl -u lead-scraper-worker -f")


if __name__ == "__main__":
    main()
