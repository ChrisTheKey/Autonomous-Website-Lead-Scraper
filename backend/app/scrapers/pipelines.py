import asyncio

import structlog

log = structlog.get_logger()


class LeadPipeline:
    """Persist scraped items to the database via asyncio bridge."""

    def process_item(self, item: dict, spider) -> dict:
        asyncio.run(self._save(item))
        return item

    async def _save(self, item: dict) -> None:
        from app.core.database import AsyncSessionLocal
        from app.models.lead import Lead

        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                __import__("sqlalchemy", fromlist=["select"]).select(Lead).where(
                    Lead.website == item.get("url")
                )
            )
            if existing.scalar_one_or_none():
                return
            lead = Lead(
                company_name=item.get("company_name") or "",
                website=item.get("url") or "",
                email=item.get("email") or None,
                phone=item.get("phone") or None,
                address=item.get("address") or None,
                raw_html=item.get("raw_html") or None,
            )
            session.add(lead)
            await session.commit()
            log.info("lead_saved", url=item.get("url"))
