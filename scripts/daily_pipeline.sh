#!/usr/bin/env bash
# Daily pipeline: scrape → enrich → export leads.csv → notify outreach agent
set -euo pipefail

PROJECT="/home/chris/Autonomous-Website-Lead-Scraper"
OUTREACH="/home/chris/Autonomer-Website-Outreach-Agent"
VENV="$PROJECT/venv/bin/python"
LOG="$PROJECT/logs/daily_pipeline.log"
LEADS_CSV="$OUTREACH/data/leads.csv"

mkdir -p "$PROJECT/logs"
exec >> "$LOG" 2>&1
echo ""
echo "=========================================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline start"
echo "=========================================="

# ── Step 1: Trigger daily scrape ──────────────────────────────────────────────
echo "[1/4] Triggering daily scrape..."
$VENV "$PROJECT/scripts/daily_scrape.py" || { echo "ERROR: scrape failed"; exit 1; }

# ── Step 2: Wait for Celery to enrich leads (crawl + analyse) ─────────────────
echo "[2/4] Waiting 3 minutes for enrichment tasks to complete..."
sleep 180

# ── Step 3: Export enriched leads to leads.csv ────────────────────────────────
echo "[3/4] Exporting leads to $LEADS_CSV ..."
$VENV "$PROJECT/export_leads.py"

# Count new leads (state=NEW)
NEW_COUNT=$(grep -c ",NEW," "$LEADS_CSV" 2>/dev/null || echo 0)
TOTAL=$(( $(wc -l < "$LEADS_CSV") - 1 ))
echo "      → $TOTAL total leads, $NEW_COUNT with state=NEW"

# ── Step 4: Write trigger file for outreach agent ─────────────────────────────
echo "[4/4] Writing trigger for outreach agent..."
TRIGGER="$OUTREACH/data/new_leads_ready.json"
cat > "$TRIGGER" <<EOF
{
  "triggered_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "new_leads": $NEW_COUNT,
  "total_leads": $TOTAL,
  "leads_csv": "$LEADS_CSV",
  "message": "New leads ready. Run /outreach start to process."
}
EOF

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline complete. $NEW_COUNT new leads ready for outreach."
