#!/usr/bin/env bash
set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Autonomous Lead Scraper — Auto Setup       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Abhängigkeiten installieren (Arch/CachyOS) ────────────────────────────────
if command -v pacman &>/dev/null; then
    echo "→ Arch/CachyOS erkannt — installiere System-Pakete..."
    sudo pacman -S --noconfirm --needed python python-pip git base-devel \
        chromium nss at-spi2-atk libdrm libxkbcommon libxcomposite \
        libxdamage libxfixes libxrandr mesa pango cairo alsa-lib 2>/dev/null || true
elif command -v apt &>/dev/null; then
    echo "→ Debian/Ubuntu erkannt — installiere System-Pakete..."
    sudo apt-get update -q && sudo apt-get install -y python3 python3-pip python3-venv git \
        chromium-browser libnss3 libatk1.0-0 libdrm2 libxkbcommon0 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libpango-1.0-0 \
        libcairo2 libasound2 2>/dev/null || true
fi

# ── Virtual Environment ────────────────────────────────────────────────────────
echo "→ Python Virtual Environment wird erstellt..."
python3 -m venv venv
source venv/bin/activate

# ── Python-Pakete ──────────────────────────────────────────────────────────────
echo "→ Python-Abhängigkeiten werden installiert..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── Playwright Browser ─────────────────────────────────────────────────────────
echo "→ Playwright Chromium wird installiert..."
playwright install chromium 2>/dev/null || true

# ── .env Datei ─────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "→ .env Datei wird erstellt..."
    cat > .env << 'ENVEOF'
DATABASE_URL=postgresql+asyncpg://neondb_owner:npg_p1w8WDghKyzN@ep-royal-night-agu7xcut.c-2.eu-central-1.aws.neon.tech/neondb?ssl=true
REDIS_URL=rediss://default:gQAAAAAAAi2pAAIgcDJiMzQ5ZTllYTY1MDM0MmE5OGJjYWY1NDU5YmY2ODljYQ@selected-snail-142761.upstash.io:6379
CELERY_BROKER_URL=rediss://default:gQAAAAAAAi2pAAIgcDJiMzQ5ZTllYTY1MDM0MmE5OGJjYWY1NDU5YmY2ODljYQ@selected-snail-142761.upstash.io:6379
CELERY_RESULT_BACKEND=rediss://default:gQAAAAAAAi2pAAIgcDJiMzQ5ZTllYTY1MDM0MmE5OGJjYWY1NDU5YmY2ODljYQ@selected-snail-142761.upstash.io:6379
GOOGLE_MAPS_API_KEY=AIzaSyC7rraZh29j0TUE4egG9r-0YywgwPnBdiY
ANTHROPIC_API_KEY=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
CLAUDE_MODEL=claude-opus-4-8
APP_ENV=development
DEBUG=false
MAX_RESULTS_PER_SEARCH=100
MAX_PAGES_PER_DOMAIN=10
GOOGLE_DATA_TTL_DAYS=30
EXPORT_REQUIRES_VERIFICATION=true
WEBHOOK_SECRET=change-me-in-production
EMAIL_VALIDATION_ENABLED=true
ENVEOF
    echo "✅ .env erstellt"
else
    echo "✅ .env bereits vorhanden — wird nicht überschrieben"
fi

# ── Datenbank-Tabellen erstellen ───────────────────────────────────────────────
echo "→ Datenbank-Tabellen werden erstellt..."
alembic upgrade head

# ── Fertig ─────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ✅ Setup abgeschlossen!                    ║"
echo "║                                              ║"
echo "║   Starten mit:                               ║"
echo "║   source venv/bin/activate                   ║"
echo "║   uvicorn app.main:app --reload              ║"
echo "║                                              ║"
echo "║   Dashboard: http://localhost:8000/dashboard ║"
echo "║   API Docs:  http://localhost:8000/docs      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
