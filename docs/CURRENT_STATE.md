# Current State

Rolling project checkpoint. Update this file when the state changes.
Last verified: 2026-08-16.

## Verified code baseline

- Commit `21a2e11ffce85354bd1c47d89d29170c60f8622a`
- Branch `giuliano/lead-scraper-development`

This is the last commit whose product code was verified by execution. Later
commits may exist that only update state documentation such as this file — a
newer `git HEAD` is therefore expected and does not invalidate anything below.
Product behaviour was last proven at the baseline above.

## Current phase

**Weak website / economic opportunity pipeline.** The `no_website` signal is
built and validated end to end. The `weak_website` signal now runs end to end
for a single company; its quality signals are still rudimentary.

## Proven end to end

Everything below was demonstrated by execution, not inferred.

- **Full search path with live Google data:** `POST /search` → search row in
  PostgreSQL → Redis → Celery search worker → Geocoding API → Places API (New) →
  classification, dedupe, scoring, compliance gate → persisted companies and
  place candidates.
- **`target=no_website` validated against real data.** Search #2 (Maler, Bern)
  ran before the target filter was fixed and stored 20 of 20 results. Search #3
  (Maler, Thun) ran after the fix and stored 2 of 20 — zero results with an own
  domain leaked through as no-website leads.
- **Crawl → analysis chain.** `POST /companies/{id}/crawl` → crawl queue →
  crawl worker → robots-respecting crawl → `crawled_pages` → automatic dispatch
  of `analyse_website_task` → analyse queue → analyse worker → signals → 
  re-classification and re-scoring. The analysis task was received 1 ms after
  the crawl returned, dispatched exactly once.
- **Company 1 (Witschi Malerei Gipserei, witschimalerei.ch)** was really
  crawled: 10 pages, robots.txt honoured, 0 blocked, all HTTP 200. The analysis
  found zero of nine weakness signals and correctly re-classified it from
  `weak_website_candidate` to `website_exists_not_target`. Recognising a healthy
  website and dropping it from the lead pool is the intended outcome.
- **Fragment URL dedupe** implemented and tested. Those 10 crawled pages were
  only 2 distinct HTTP resources; fragment variants now collapse before the
  visited check. 12 targeted tests, including a regression case built from the
  10 real URLs.
- **Infrastructure survives restarts.** After a Docker Desktop and Windows
  restart, the `pgdata` and `redisdata` volumes and all rows were intact.

## Current data state

Read from the live database, read-only:

| | |
|---|---|
| searches | 3 — #1 `queued` (0 companies), #2 `completed` (20), #3 `completed` (2) |
| companies | 22 |
| — `weak_website_candidate` / `website_found` | 18 |
| — `no_website_candidate` / `no_website` | 3 |
| — `website_exists_not_target` / `website_analyzed` | 1 (company 1, the crawl test) |
| place_candidates | 22 |
| crawled_pages | 10 (all company 1) |
| contacts | 0 |
| audit_logs | 24 |
| suppression_list | 0 |
| status | all 22 `needs_review`, 0 `verified`, 0 `can_export` |
| alembic | `0001` |
| Redis queues | default `celery` 1 · search 0 · crawl 0 · analyse 0 · refresh 0 |

Containers running: postgres, redis, api, worker-search, worker-crawl,
worker-analyse. Not running: flower, migrate.

## Engineering infrastructure

Committed to the repository, so every session and machine gets it:

- `CLAUDE.md` — how to work here (stable).
- `docs/CURRENT_STATE.md` — this file, where the project stands (moving).
- `.claude/skills/codebase-memory/` — structural code queries over a knowledge
  graph instead of broad grep. Documents the MCP tool surface only.
- `.claude/skills/loop-engineering/` — designing and reviewing autonomous agent
  loops. Its four `references/` files load on demand, not into initial context.

Both skills are vendored byte-identical from upstream (MIT), committed and
pushed. `evals/` was deliberately excluded.

### Local development environment (Giuliano's Windows machine only)

Not part of the repository and not portable — a fresh clone on another machine
has the skills but none of the following:

- `codebase-memory-mcp` **v0.10.4** installed at
  `%LOCALAPPDATA%\Programs\codebase-memory-mcp\codebase-memory-mcp.exe`
- Pinned to the audited upstream commit `c0bd4bb`: release tag `v0.10.4` points
  exactly at it. `releases/latest` already serves v0.10.5 and was **not** used.
- The release asset's SHA-256 was verified against the tag's `checksums.txt`
  before extraction, and the archive contents were checked against the
  installer's own allowlist. Only the binary was extracted.
- Build provenance was **not** verified — the Sigstore/SLSA bundles ship with
  the release, but neither `gh` nor `cosign` is installed. Release integrity is
  proven; "compiled from that source" is not.
- MCP configured in **local/project scope** only: `~/.claude.json` under
  `projects["C:/Users/Bucherer/Autonomous-Website-Lead-Scraper"].mcpServers`,
  one entry `codebase-memory` pointing at the absolute binary path. A timestamped
  backup of that config was taken first; a structural diff confirmed exactly one
  added key.
- Deliberately **not** done: no global hooks, no global skills, no global agent
  files, no `~/.claude/settings.json`, no PATH change, no Codex configuration.
  The upstream installer would have written 15 files across Claude Code and
  Codex; it was never run.
- The repository is **not indexed yet**, and no MCP tool has been called.

The long-running session that set this up had already started before the MCP
entry existed, so it never loaded the server. **A fresh session is required**
before `codebase-memory` is available.

## Known open issues

Confirmed by inspection or execution. No hypothetical entries.

- **`test_suppression.py::test_no_identifiers_returns_not_suppressed` fails.**
  Pre-existing test defect, not a code bug: the fixture sets `id = 1`, so
  `is_suppressed` builds a company_id filter, the early return is skipped, and
  the unconfigured `AsyncMock` returns a truthy row. The test could never run
  before the circular import was fixed. Production code is byte-identical to
  its original.
- **`refresh` queue has no worker.** `refresh_company_task` routes there
  correctly, but `docker-compose.yml` defines no `-Q refresh` service, so
  refresh jobs would queue forever.
- **Search #1 is stuck at `queued`** with a message still sitting in the default
  `celery` queue. Both are deliberate historical artefacts from before the queue
  routing fix. Do not consume, move or clean them without asking.
- **Search → crawl is deliberately not automatic.** The orchestrator never
  dispatches a crawl; its docstring claims it does. Entry is the manual endpoint
  only. This is intentional until crawling is validated more broadly.
- **Weak website signals are rudimentary.** Nine signals exist; four score
  (`no_https`, `unreachable`/`http_error`, `no_mobile_viewport`,
  `no_contact_page`, plus `construction_page` sharing a bucket), four set
  `is_weak` but award no points (`no_contact_info`, `old_copyright`,
  `slow_load`, `no_crawlable_content`). `no_https` is a URL prefix check, not a
  TLS check. Missing entirely: impressum as a legal signal, CTA/conversion
  elements, real performance, outdated tech, broken links, trust signals.
- **Contacts, export and CRM are unfinished.** The extractor writes contacts,
  but the CSV export has no contact columns, so they never leave the system.
  `mark_contacted` does not re-evaluate `can_export` despite its comment. No CRM
  integration in the active tree.
- **Geocoding runs inside the pagination loop** in `places_service.py`, costing
  one extra Geocoding request per page. Deferred cost fix.
- **Score before analysis is meaningless** for weak candidates: an own domain
  always yields 0 (a −60 penalty on optimistic defaults), a social-only site
  always 35. Only post-analysis scores carry information.
- **The crawler has no JavaScript engine.** Content a hashbang SPA renders
  client-side is unreachable. Documented, not a bug to fix.
- **No authentication on any endpoint**, and CORS is `*`. Acceptable locally,
  blocking for any deployment.

## Do not touch yet

- Automatic mass crawling
- CRM outreach
- Production deployment
- Large scoring changes
- Legacy `backend/` and `frontend/`

## Next goal

The engineering infrastructure is in place; the next steps exercise it.

1. **End the long session and open a fresh one** in this repository, using only
   `CLAUDE.md` and this file as project memory.
2. **Test the MCP connection.** `list_projects` and `index_status` are the
   cheapest checks; both should report that nothing is indexed yet.
3. **Index the repository once** with codebase-memory.
4. **Verify the graph against the source** on architecture relationships already
   known from this session — for example that `dedupe_service` imports
   `write_audit` from `compliance_service` while `compliance_service` imports
   only from `normalization` (no cycle), that `crawl_company_task` dispatches
   `analyse_website_task`, and that `run_search` calls `matches_target`. If the
   graph disagrees with the source, trust the source.
5. **Second controlled single-website test**, on a company with a classic
   multi-page site, to show the crawl budget reclaimed by the fragment fix and
   to produce the first non-zero weak-website signal set.
6. **Watch context and tool usage** during that test as the first efficiency
   benchmark for the new loop.

Before step 5, `worker-crawl` and `worker-analyse` need `--force-recreate` so
they load the current code.

## Important decisions

Load-bearing, and they shape what "correct" means here.

- **Quality over volume.** A smaller set of real leads beats a large list.
  Yield fell from an apparent 100% to a real 5–10% per search when the target
  filter was fixed — that is the honest number, and it is the right one.
- **Economic signals, not data collection.** A lead exists because there is a
  business reason to sell, not because a record could be stored.
- **`no_website` is signal 1, `weak_website` is signal 2.** Neither is the whole
  product.
- **A later economic opportunity engine** is intended to combine digital gap,
  business value, demand, reachability, timing and sales feedback. Current
  scoring is a precursor, not that engine.
- **Auto-crawl only after controlled validation.** Crawling third-party servers
  at scale is not something to switch on speculatively.
- **Compliance gates are a feature, not friction.** Manual verification before
  export, audit logs on every action, robots.txt respected, no data invented.
