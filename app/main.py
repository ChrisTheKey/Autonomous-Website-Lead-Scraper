from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api import candidates, companies, exports, reviews, searches
from app.config import settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", env=settings.app_env)
    yield
    log.info("shutdown")


app = FastAPI(
    title="B2B Lead Discovery Service",
    description=(
        "Legal B2B lead discovery for local businesses without websites. "
        "Powered by Google Places API. Compliant by design."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(searches.router, tags=["search"])
app.include_router(companies.router, tags=["companies"])
app.include_router(reviews.router, tags=["review-actions"])
app.include_router(candidates.router, tags=["candidates"])
app.include_router(exports.router, tags=["export"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    """Simple HTML dashboard for lead review."""
    return HTMLResponse(content=_DASHBOARD_HTML)


_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lead Discovery Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-900">
<div class="max-w-7xl mx-auto px-4 py-8">
  <h1 class="text-3xl font-bold mb-2">Lead Discovery Dashboard</h1>
  <p class="text-gray-500 mb-6">Lokale Unternehmen ohne Website finden und verwalten.</p>

  <!-- Search Form -->
  <div class="bg-white rounded-lg border border-gray-200 p-6 mb-8 shadow-sm">
    <h2 class="text-lg font-semibold mb-4">Neue Suche starten</h2>
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-4">
      <input id="industry" placeholder="Branche z.B. Coiffeur" class="border rounded px-3 py-2 text-sm"/>
      <input id="location" placeholder="Ort z.B. Zürich" class="border rounded px-3 py-2 text-sm"/>
      <input id="radius" type="number" value="10" placeholder="Radius km" class="border rounded px-3 py-2 text-sm"/>
      <input id="max_results" type="number" value="50" placeholder="Max. Ergebnisse" class="border rounded px-3 py-2 text-sm"/>
    </div>
    <input id="keywords" placeholder="Keywords (kommagetrennt, optional)" class="border rounded px-3 py-2 text-sm w-full mb-4"/>
    <button onclick="startSearch()" class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 text-sm font-medium">
      Suche starten
    </button>
    <span id="search-status" class="ml-4 text-sm text-gray-500"></span>
  </div>

  <!-- Tabs -->
  <div class="mb-4 flex gap-2 flex-wrap">
    <button onclick="loadLeads('no_website_candidate','high_priority')" class="tab-btn bg-red-100 text-red-800 px-3 py-1 rounded text-sm font-medium">🔥 Kein Website (High)</button>
    <button onclick="loadLeads('no_website_candidate','medium_priority')" class="tab-btn bg-orange-100 text-orange-800 px-3 py-1 rounded text-sm font-medium">⚡ Kein Website (Medium)</button>
    <button onclick="loadLeads('weak_website_candidate',null)" class="tab-btn bg-yellow-100 text-yellow-800 px-3 py-1 rounded text-sm font-medium">⚠️ Schwache Website</button>
    <button onclick="loadLeads(null,'needs_review',true)" class="tab-btn bg-blue-100 text-blue-800 px-3 py-1 rounded text-sm font-medium">📋 Needs Review</button>
    <button onclick="loadLeads(null,'verified',true)" class="tab-btn bg-green-100 text-green-800 px-3 py-1 rounded text-sm font-medium">✅ Verified</button>
    <button onclick="loadLeads(null,'contacted',true)" class="tab-btn bg-purple-100 text-purple-800 px-3 py-1 rounded text-sm font-medium">📞 Contacted</button>
    <button onclick="loadLeads(null,'rejected',true)" class="tab-btn bg-gray-100 text-gray-800 px-3 py-1 rounded text-sm font-medium">❌ Rejected</button>
    <button onclick="loadLeads(null,'suppressed',true)" class="tab-btn bg-gray-200 text-gray-600 px-3 py-1 rounded text-sm font-medium">🚫 Suppressed</button>
    <a href="/export/no-website-candidates" class="bg-emerald-600 text-white px-3 py-1 rounded text-sm font-medium ml-auto">⬇ Export CSV</a>
  </div>

  <!-- Table -->
  <div class="overflow-x-auto rounded-lg border border-gray-200 shadow-sm bg-white">
    <table class="min-w-full divide-y divide-gray-200 text-sm">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Name</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Branche</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Ort</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Score</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Lead Typ</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Status</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Tel</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Adresse</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Export</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Aktionen</th>
        </tr>
      </thead>
      <tbody id="lead-tbody" class="divide-y divide-gray-100 bg-white">
        <tr><td colspan="10" class="text-center py-8 text-gray-400">Tab auswählen um Leads zu laden…</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
const API = "";

const LEAD_TYPE_LABELS = {
  no_website_candidate: "🔴 Kein Website",
  weak_website_candidate: "🟡 Schwache Website",
  website_exists_not_target: "🟢 Website vorhanden",
  invalid_or_risky: "⚫ Ungültig",
};

const STATUS_COLORS = {
  needs_review: "bg-blue-100 text-blue-800",
  verified: "bg-green-100 text-green-800",
  rejected: "bg-gray-100 text-gray-700",
  contacted: "bg-purple-100 text-purple-800",
  suppressed: "bg-red-100 text-red-700",
  discovered: "bg-yellow-100 text-yellow-800",
};

async function startSearch() {
  const industry = document.getElementById("industry").value;
  const location = document.getElementById("location").value;
  const radius_km = parseInt(document.getElementById("radius").value) || 10;
  const max_results = parseInt(document.getElementById("max_results").value) || 50;
  const kw = document.getElementById("keywords").value;
  const keywords = kw ? kw.split(",").map(s => s.trim()).filter(Boolean) : [];

  document.getElementById("search-status").textContent = "Wird gestartet…";
  const resp = await fetch(`${API}/search`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({industry, location, radius_km, max_results, keywords, target: "no_website"})
  });
  const data = await resp.json();
  document.getElementById("search-status").textContent = resp.ok
    ? `✓ Suche #${data.id} gestartet (${data.status})`
    : `Fehler: ${JSON.stringify(data)}`;
}

async function loadLeads(lead_type, priorityOrStatus, isStatus = false) {
  const params = new URLSearchParams({limit: 100});
  if (lead_type) params.set("lead_type", lead_type);
  if (isStatus && priorityOrStatus) params.set("status", priorityOrStatus);
  else if (priorityOrStatus) params.set("priority", priorityOrStatus);

  const resp = await fetch(`${API}/companies?${params}`);
  const leads = await resp.json();

  const tbody = document.getElementById("lead-tbody");
  if (!leads.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center py-8 text-gray-400">Keine Leads gefunden.</td></tr>`;
    return;
  }

  tbody.innerHTML = leads.map(l => `
    <tr class="hover:bg-gray-50">
      <td class="px-4 py-3 font-medium">${l.name}</td>
      <td class="px-4 py-3 text-gray-600">${l.industry || "—"}</td>
      <td class="px-4 py-3 text-gray-600">${l.location || "—"}</td>
      <td class="px-4 py-3 font-bold ${l.website_opportunity_score >= 70 ? "text-red-600" : l.website_opportunity_score >= 40 ? "text-orange-500" : "text-gray-500"}">${l.website_opportunity_score}</td>
      <td class="px-4 py-3">${LEAD_TYPE_LABELS[l.lead_type] || l.lead_type}</td>
      <td class="px-4 py-3"><span class="rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_COLORS[l.status] || ""}">${l.status}</span></td>
      <td class="px-4 py-3">${l.phone ? "✓" : "—"}</td>
      <td class="px-4 py-3 text-gray-500 max-w-[150px] truncate">${l.address || "—"}</td>
      <td class="px-4 py-3">${l.can_export ? "✅" : `<span title="${l.export_block_reason || ""}">🔒</span>`}</td>
      <td class="px-4 py-3 flex gap-1">
        <button onclick="action(${l.id},'verify')" class="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded hover:bg-green-200">✓</button>
        <button onclick="action(${l.id},'reject')" class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded hover:bg-red-200">✗</button>
        <button onclick="action(${l.id},'mark-contacted')" class="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded hover:bg-purple-200">📞</button>
        <button onclick="suppress(${l.id})" class="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded hover:bg-gray-300">🚫</button>
        <button onclick="action(${l.id},'refresh')" class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded hover:bg-blue-200">↻</button>
      </td>
    </tr>
  `).join("");
}

async function action(id, endpoint) {
  const resp = await fetch(`${API}/companies/${id}/${endpoint}`, {method: "POST"});
  if (resp.ok) {
    const row = document.querySelector(`tr button[onclick="action(${id},'verify')"]`)?.closest("tr");
    if (row) row.style.opacity = "0.5";
  } else {
    alert("Fehler: " + await resp.text());
  }
}

async function suppress(id) {
  const reason = prompt("Grund für Unterdrückung:");
  if (!reason) return;
  const resp = await fetch(`${API}/companies/${id}/add-to-suppression`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({reason})
  });
  if (!resp.ok) alert("Fehler: " + await resp.text());
}
</script>
</body>
</html>
"""
