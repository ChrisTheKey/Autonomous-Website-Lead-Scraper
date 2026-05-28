"""
Streamlit dashboard for monitoring and managing leads.
Run with: streamlit run dashboard.py
"""

import asyncio

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Lead Scraper Dashboard", layout="wide")
st.title("Autonomous Lead Scraper – Dashboard")


@st.cache_data(ttl=30)
def load_leads() -> pd.DataFrame:
    import asyncio
    from sqlalchemy import select, text
    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead

    async def _fetch():
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Lead).order_by(Lead.created_at.desc()).limit(500))
            leads = result.scalars().all()
            return [
                {
                    "ID": l.id,
                    "Company": l.company_name,
                    "Website": l.website,
                    "Email": l.email,
                    "Phone": l.phone,
                    "City": l.city,
                    "Country": l.country,
                    "Status": l.status.value if l.status else "",
                    "CRM": l.crm_source,
                    "Created": l.created_at,
                }
                for l in leads
            ]

    return pd.DataFrame(asyncio.run(_fetch()))


# ── Sidebar filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    status_filter = st.multiselect(
        "Status",
        options=["new", "enriched", "qualified", "synced", "rejected"],
        default=["new", "enriched", "qualified"],
    )
    country_filter = st.text_input("Country contains")

# ── Load & filter ────────────────────────────────────────────────────────────
df = load_leads()
if not df.empty:
    if status_filter:
        df = df[df["Status"].isin(status_filter)]
    if country_filter:
        df = df[df["Country"].str.contains(country_filter, case=False, na=False)]

# ── KPI cards ────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Leads", len(df))
col2.metric("Qualified", len(df[df["Status"] == "qualified"]) if not df.empty else 0)
col3.metric("Synced to CRM", len(df[df["Status"] == "synced"]) if not df.empty else 0)
col4.metric("Rejected", len(df[df["Status"] == "rejected"]) if not df.empty else 0)

st.divider()

# ── Scrape new URL ────────────────────────────────────────────────────────────
with st.expander("Scrape a new URL"):
    new_url = st.text_input("Target URL", placeholder="https://example.com")
    use_browser = st.checkbox("Use browser (Playwright)", value=False)
    crm_target = st.selectbox("Sync to CRM", ["hubspot", "pipedrive", "salesforce"])
    if st.button("Start scrape & process"):
        import httpx
        with st.spinner("Queuing job…"):
            try:
                r = httpx.post(
                    "http://localhost:8000/api/scraper/",
                    json={"url": new_url, "use_browser": use_browser},
                    timeout=10,
                )
                st.success(f"Job queued: {r.json()}")
            except Exception as e:
                st.error(str(e))

# ── Lead table ────────────────────────────────────────────────────────────────
st.subheader("Leads")
if df.empty:
    st.info("No leads found. Start scraping!")
else:
    st.dataframe(df, use_container_width=True, hide_index=True)

# ── Status distribution chart ─────────────────────────────────────────────────
if not df.empty:
    st.subheader("Status Distribution")
    chart_data = df["Status"].value_counts().reset_index()
    chart_data.columns = ["Status", "Count"]
    st.bar_chart(chart_data.set_index("Status"))
