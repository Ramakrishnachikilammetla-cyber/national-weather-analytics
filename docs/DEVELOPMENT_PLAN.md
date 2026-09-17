# Development plan

Phased implementation for a **student hackathon MVP**, then production-shaped Kafka/Spark/ML. Do not skip foundation. Do not implement unauthorized scraping. Do not treat ML as a true/fake oracle.

**MVP event categories:** rainfall, thunderstorms, flooding, heatwaves, fog, dust storms, strong winds. Extra categories stay in the lookup table as `mvp=false` until a later phase.

---

## Phase 0 — Foundation

**Goal:** Repo and contracts so every later piece plugs in.

**Deliverables**

- Keep `docs/` (this set) as the source of truth.
- Choose runtime: Python 3.12+, Node LTS, PostgreSQL 16 + PostGIS.
- Intended tree: `apps/api`, `apps/web`, `ingest/adapters`, `db/migrations`, `tests`, `infra` (create when coding starts).
- `.env.example` with **no secrets**; document Open-Meteo (no key) vs APIs that need keys.
- Seed list of `event_categories` and roles.

**Out of scope:** Kafka cluster, Spark, React features, live ingest.

---

## Phase 1 — Backend core

**Goal:** FastAPI + Postgres/PostGIS with auth and empty-but-real tables.

**Deliverables**

- Migrations for entities in [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) (can defer M:N event link tables if time-boxed, but users, sources, observations, reports, ml_scores, verification_reviews should exist).
- `GET /health`, `/ready`, `/auth/register`, `/auth/login`, `/auth/me`.
- Seed admin user via env (not hardcoded password in git).
- `GET /categories`, `/geo/states` (states can start as a small official/open seed; full polygons when a dataset is added).
- RBAC middleware.

**Out of scope:** Full dashboard, Spark, social ingest.

---

## Phase 2 — Frontend shell

**Goal:** React app that talks to real auth and placeholder pages (no fake weather numbers).

**Deliverables**

- Login, register, logout.
- Layout: Dashboard, Map, Submit report, Admin (routes gated by role).
- Empty states: “No data yet” until ingest exists.
- Shared filter controls wired to query params (even if API returns empty lists).

**Out of scope:** Polished viz, choropleth with invented counts.

---

## Phase 3 — Data ingestion (v0, no Kafka required)

**Goal:** One pluggable adapter + citizen reports landing in Postgres.

**Deliverables**

- Adapter interface (`fetch` → `normalize` → `upsert`).
- **v0 source:** Open-Meteo for a configurable set of Indian points **or** one permitted IMD/data.gov.in dataset.
- `POST /reports` persisted with `pending_review`.
- `GET /observations`, `GET /reports` with date/location/category filters.
- `ingest_runs` rows for each job.
- Idempotent upserts (unique keys).
- India bounding-box QC flag.

**Out of scope:** Scraping; additional APIs unless time remains (second adapter proves plug-in design).

---

## Phase 4 — Kafka and Spark (architecture on, production later)

**Goal:** Introduce the bus and jobs **without** blocking the hackathon demo. Demo can still use Phase 3 direct writes.

**4a — Practical (hackathon if time)**

- Docker Compose **optional** Kafka + a producer that mirrors new reports/observations to `raw.*`.
- Document topic names from [ARCHITECTURE.md](./ARCHITECTURE.md).

**4b — Full (post-hackathon / later)**

- All adapters produce to Kafka.
- Spark batch: clean, duplicate detection, rule-based classification into MVP categories.
- Spark streaming later for rolling analytics tables.
- FastAPI remains the query layer; it does not scrape.

**Out of scope for 4a:** Multi-AZ clusters, schema registry mandatory (can add later).

---

## Phase 5 — ML evidence scoring

**Goal:** Confidence + evidence JSON; **human review unchanged.**

**Deliverables**

- Feature sketch: source trust, nearby observation thresholds (e.g. rain mm, wind m/s, visibility), count of nearby same-category reports in a time window.
- Write `ml_scores` only; **never** auto-update `verification_status` to confirmed/rejected.
- `GET` report/event detail returns latest score for analysts.
- Version string on the model (`model_version`).

**Out of scope:** Claiming “fake news detection” as ground truth; training on scraped social graphs.

---

## Phase 6 — Dashboard

**Goal:** Analyst/public view of **real** ingested data.

**Deliverables**

- `/analytics/summary` and `/analytics/timeseries` implemented and charted.
- Filters: date, MVP category, state/district, verification status, optional `min_confidence`.
- Recent reports/events table from API (no hardcoded rows).
- Polling interval for near-real-time (e.g. 30s) until SSE exists.

**Out of scope:** Fake KPIs when the database is empty.

---

## Phase 7 — Admin panel

**Goal:** Operate the MVP without SQL.

**Deliverables**

- Review queue + review actions (`confirmed`, `disputed`, `rejected`, `needs_more_info`) with notes and audit log.
- User list/role/disable (admin).
- Source enable/disable + trigger ingest run.
- Ingest run history.

**Out of scope:** Full CMS, arbitrary SQL console.

---

## Phase 8 — India map and geospatial analytics

**Goal:** Map is a first-class filter and display.

**Deliverables**

- Load official/open India state (then district) boundaries into PostGIS.
- `GET /map/points` and `/map/choropleth`.
- Click point → report/event detail.
- Bbox filter from map bounds.

**Out of scope:** 3D globes; unofficial scraped tile dumps that violate TOS (use OSM/MapLibre with compliant tiles).

---

## Phase 9 — Testing

**Goal:** Confidence the MVP is real, not a demo of mocks.

**Deliverables**

- API tests: auth, report create, forbidden admin routes, filter 400s.
- Unit tests: category codes, bbox QC, duplicate key behavior.
- Geo test: point classified into a known district (when boundaries exist).
- Frontend smoke: login + empty dashboard + submit validation.
- Mock external HTTP for Open-Meteo.

**Out of scope:** Load tests at national scale (optional later).

---

## Phase 10 — Deployment

**Goal:** Another machine can run the hackathon stack.

**Deliverables**

- `infra/docker-compose.yml`: `web`, `api`, `db` (PostGIS).
- Optional profile: `kafka`, `spark` (later).
- README: how to migrate, seed admin, run one ingest, open UI.
- Environment-based secrets.

**Out of scope:** Production SRE (autoscaling, multi-region) unless the event requires it.

---

## Suggested hackathon slice (if time is short)

Ship **Phases 0–3, 6 (minimal), 7 (review queue only), 8 (points only), 9 (API tests), 10 (compose without Kafka)**.

Keep Kafka/Spark/ML/choropleth as demos of the **documented** later path, not as fake screens.

---

## Dependencies between phases

```text
0 Foundation
    → 1 Backend
        → 2 Frontend shell
        → 3 Ingest + reports
              → 6 Dashboard (needs data + APIs)
              → 7 Admin review
              → 8 Map (needs PostGIS + data)
              → 5 ML scores (needs reports/observations)
              → 4 Kafka/Spark (can lag; same DB)
    → 9 Testing (throughout; gate before 10)
    → 10 Deployment
```

---

## Definition of done (MVP)

- A permitted weather source and citizen reports both appear on the map/dashboard.
- Filters use the seven problem-statement categories.
- Admin can confirm or reject a report; ML if present only shows confidence/evidence.
- No scraping modules in the repo.
- Compose brings up API + DB + web.

---

## Related docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DATABASE_DESIGN.md](./DATABASE_DESIGN.md)
- [API_DESIGN.md](./API_DESIGN.md)
