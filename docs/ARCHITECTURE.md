# Architecture — National Weather Big Data Analytics Platform (India)

This document describes the **intended** system architecture. It is not an implementation. No application code is assumed to exist yet.

**Product:** ingest, verify, store, and visualize weather-related events across India from official APIs, permitted public datasets, permitted public feeds, and citizen-submitted reports.

**MVP audience:** student hackathon — a working slice (ingest → store → API → map/dashboard → admin review) before full Kafka/Spark production clusters.

---

## 1. Goals and non-goals

### Goals

- Cover India with date, event, location, and verification filters.
- Use **only** official APIs, licensed/open public datasets, permitted public APIs (vendor ToS), and first-party citizen reports.
- Keep sources **pluggable**: a new adapter must not require rewriting Kafka, Spark, or the API.
- Treat AI/ML as a **confidence and evidence** signal. Humans (admins/analysts) make verification decisions.
- Support real-time *and* batch paths; Kafka and Spark are first-class in the design, with a **direct ingest fallback** for v0.

### Non-goals (this architecture / MVP)

- Building the complete application in one phase.
- Unauthorized web scraping, unofficial mirrors, or harvesting private social accounts.
- Blind true/fake labels from a model with no human review.
- Running a production multi-broker Kafka cluster and YARN/K8s Spark farm on day one.

---

## 2. Principles

1. **Adapter in, common schema out.** Every source maps to internal records (`Observation`, `PublicPost`, `CitizenReport`, later `WeatherEvent`).
2. **Official data is quality-checked, not “verified social.”** Station/API observations get QC flags (range, bounds, missing). Citizen and public-feed items get corroboration scores plus admin status.
3. **India geography is first-class.** Coordinates, stations, districts, and states live in PostGIS.
4. **Least privilege.** Citizens submit and view; analysts review; admins manage users, sources, and moderation.
5. **License and attribution stay with the record.** Each row stores `source_id` and, where required, dataset/API attribution.

---

## 3. High-level topology

```text
┌─────────────────────────────────────────────────────────────────┐
│ Sources (pluggable adapters)                                      │
│  Official weather APIs │ Public datasets │ Permitted public feeds │
│  Citizen reports (React → FastAPI)                                │
└───────────────────────────────┬─────────────────────────────────┘
                                │ normalize
                ┌───────────────┴───────────────┐
                │ v0: FastAPI / ingest workers   │
                │ later: Kafka producers         │
                └───────────────┬───────────────┘
                                ▼
                    Apache Kafka (later phases)
                    topics: raw / cleaned / classified / verified / dlq
                                │
                                ▼
                    Apache Spark (later phases)
                    clean → dedupe → classify → ML evidence
                                │
                                ▼
                    PostgreSQL + PostGIS (system of record)
                                │
                                ▼
                    FastAPI  ──►  React (dashboard, India map, reports, admin)
```

**v0 practical path:** adapters write through FastAPI or a small worker **directly into PostgreSQL**, with the same normalizers Spark will reuse later. Kafka/Spark become the production bus without changing the public API or DB schema.

---

## 4. Weather event categories

### MVP primary categories (problem statement)

| Code            | Meaning                                      |
|-----------------|----------------------------------------------|
| `rainfall`      | Rain / heavy rain related                    |
| `thunderstorms` | Thunderstorm activity                        |
| `flooding`      | Inland/urban/river flooding                  |
| `heatwaves`     | Extreme heat                                 |
| `fog`           | Dense fog / visibility reduction             |
| `dust_storms`   | Dust / sand storm                            |
| `strong_winds`  | High wind / gust events                      |

Storage uses these snake_case codes. UI may show human labels.

### Future extensibility (not MVP filters)

`cyclone`, `hail`, `drought_related`, `other`. Schema and APIs should accept an extensible enum so these can be enabled without a redesign.

Classification may assign **one primary category** and optional **secondary tags**.

---

## 5. Data sources (modular)

Each source is an **adapter** with: fetch, parse, map to internal schema, respect rate limits, record license/attribution, emit failures to a dead-letter path.

### 5.1 Official weather APIs (candidates)

| Source | Role | Notes |
|--------|------|--------|
| IMD / Open Government Data (`data.gov.in`) | National official products | Use **published APIs or downloadable datasets** only |
| Open-Meteo | Forecast + historical for Indian lat/lon | Open license; good **v0 default** for station-like grids |
| NASA POWER | Agroclimatology / radiation / temp | Official API, terms apply |
| Copernicus CDS (ERA5) | Reanalysis | Use only with CDS licence |

**v0 default:** Open-Meteo (or one official downloadable IMD/data.gov.in dataset) + citizen reports. Additional APIs are extra adapters.

### 5.2 Public datasets

Examples: IMD gridded rainfall/temperature where redistribution is allowed; GHCN-style station series; open government CSVs. Ingest as **batch files** (S3/local `data/raw/` later), not as scraped HTML.

### 5.3 Permitted social / public sources

- Only **official agency accounts or official RSS/Atom** via that platform’s **public API and Terms of Service** (e.g. IMD, NDMA, state disaster authorities).
- Store platform post ID, URL, fetched_at, and raw payload (if licence allows).
- **Do not** scrape HTML, bypass logins, or collect private/user timelines.

MVP may **omit** social ingest entirely and keep the `public_posts` table + adapter interface ready.

### 5.4 Citizen reports

Submitted in-app with consent: time, location (map or GPS), category, description, optional media, contact optional. These are **claims**, not ground truth, until an analyst/admin sets verification status. ML only adds a score and evidence list.

### Adding a source later

1. Implement `ingest/adapters/<name>/`.
2. Register row in `weather_sources`.
3. Map to the shared envelope (see below).
4. Produce to `raw.*` (or v0 insert API).
5. No changes required to React filter contracts if categories and geo fields stay stable.

---

## 6. Canonical envelopes (logical)

All adapters emit one of:

- **Observation** — measured or forecast values (temp, rain mm, wind, visibility, etc.) at a point/time.
- **CitizenReport** — human-submitted event claim.
- **PublicPost** — permitted official public message, possibly mentioning weather.

Spark (or v0 workers) may **promote** corroborated items into **WeatherEvent** (aggregated incident for the dashboard).

Shared fields: `source_id`, `observed_at` (timestamptz, stored UTC, displayed IST), `geometry` (Point), optional `state_code` / `district_code`, `raw_payload` (JSONB), `ingested_at`.

---

## 7. Ingestion

- **Pull adapters:** scheduled (cron / later Airflow) for APIs and datasets.
- **Push:** citizen reports via `POST /api/v1/reports`.
- **Idempotency:** natural keys (`source_id` + external id + timestamp) so retries do not duplicate.
- **India bounding box / admin clip:** drop or flag points outside India (and documented maritime EEZ if needed later).
- **Units:** SI internally (°C, mm, m/s, metres visibility).

v0: Python functions called from FastAPI or a CLI. Later: same functions as Spark UDFs/jobs.

---

## 8. Apache Kafka

Included in the architecture; **full production deployment is a later phase.**

### Logical topics

| Topic | Payload |
|-------|---------|
| `raw.observations` | Adapter output |
| `raw.citizen_reports` | After API accept |
| `raw.public_posts` | Permitted feeds |
| `cleaned.events` | After QC |
| `classified.events` | Category codes |
| `verified.signals` | ML confidence + evidence (not final truth) |
| `dlq.*` | Poison messages |

### v0 vs later

| Phase | Bus |
|-------|-----|
| Foundation–ingestion | Direct DB writes; optional in-process queue |
| Kafka/Spark phase | Producers on adapters; consumers in Spark; FastAPI may still write reports to `raw.citizen_reports` |

Realtime analytics later: Spark streaming aggregates → Postgres or a serving table; UI polls or WebSocket/SSE from FastAPI.

---

## 9. Apache Spark

Jobs (batch first, streaming later):

1. **Clean** — timezone, units, India clip, range checks (e.g. implausible temperature), required fields.
2. **Duplicate detection** — exact key duplicates; near-duplicates for reports (Haversine + time window + same category / similar text hash).
3. **Classification** — map observations and text to MVP categories (rules first: thresholds for rain, wind, visibility, heat; keyword rules for posts). ML classifier is optional later.
4. **ML evidence scoring** — features: source trust, distance to nearest station observation, count of nearby reports, text/image model outputs if present. Output: `confidence` in `[0, 1]`, `evidence` JSON, **never** auto-set `verification_status` to true/fake.

Spark does **not** replace admin review.

---

## 10. Data cleaning, duplicates, classification

| Step | Rule of thumb |
|------|----------------|
| Cleaning | Null handling; clip to India; IST display / UTC store; outlier flags (`qc_flags`) |
| Duplicates | Unique constraint on source natural key; report clusters stored as `duplicate_of_id` |
| Classification | Primary category ∈ MVP set; low-confidence → `unclassified` holding state until rules/ML/admin assign |

---

## 11. AI/ML verification (confidence, not verdict)

**Outputs per report/post (and optionally per derived event):**

- `ml_confidence` ∈ [0, 1]
- `ml_evidence` JSON (e.g. `{ "nearby_station_rain_mm": 42, "corroborating_reports": 3, "source_trust": 0.9 }`)
- `ml_model_version`
- `ml_scored_at`

**Does not output:** a boolean “fake” that is stored as truth.

**Human workflow:**

```text
submitted → ml_scored (optional) → pending_review → 
  admin/analyst: confirmed | disputed | rejected | needs_more_info
```

Dashboard filters use **human `verification_status`** and can optionally filter by **minimum ml_confidence**. High ML score never bypasses `pending_review` for citizen/public items.

Official observations: QC only (`qc_status`), not this social-verification workflow.

---

## 12. PostgreSQL / PostGIS

System of record for users, sources, stations, observations, reports, posts, events, verification, India polygons, ingest/audit.

PostGIS: `GEOGRAPHY(Point, 4326)` for points; `GEOMETRY` for state/district polygons; GIST indexes; `ST_DWithin`, `ST_Contains` for map and corroboration.

See [DATABASE_DESIGN.md](./DATABASE_DESIGN.md).

---

## 13. FastAPI backend

- REST under `/api/v1/` (see [API_DESIGN.md](./API_DESIGN.md)).
- JWT auth; role-based access (citizen, analyst, admin).
- Query layer: filters (datetime range, category, bbox or state/district, verification status, ml_confidence).
- Writes: reports, admin moderation, source config.
- Read-only aggregations for dashboard KPIs.
- Optional later: WebSocket/SSE `/api/v1/stream/events` fed from Kafka or LISTEN/NOTIFY.

---

## 14. React frontend

| Surface | Purpose |
|---------|---------|
| Public dashboard | Counts, time series, recent events, filters |
| India map | Points and choropleth (district/state); click for detail |
| Report form | Citizen submission |
| Admin panel | Users, sources, moderation queue, ingest health, audit |

Shared filter state: date range, category (MVP seven), location (state/district/map), verification status.

---

## 15. Dashboard, map, filters, realtime

- **Dashboard:** totals by category, last-N-hours vs last-N-days, map widget, table.
- **Map:** India outline + districts when boundary data is loaded (e.g. official/open GeoJSON). No fabricated coordinates.
- **Filters:** `from`, `to`, `category`, `state_code`, `district_code`, `bbox`, `verification_status`, `min_confidence`.
- **Realtime (later):** poll every N seconds in v0; push when Kafka streaming exists.

---

## 16. Authentication and admin access

- Register/login (citizens); seed or invite **admin**.
- Roles: `citizen`, `analyst`, `admin`.
- Analyst: review queue, set verification status.
- Admin: all analyst permissions + users, source enable/disable, job triggers.
- Passwords hashed (e.g. Argon2/bcrypt); JWT access (+ refresh later).
- Audit log for moderation and source changes.

---

## 17. Testing

| Layer | Focus |
|-------|--------|
| Unit | Normalizers, QC rules, category mapping, duplicate window |
| API | Auth, report create, filter queries, admin-only 403 |
| Geo | Point-in-district, bbox |
| Contract (later) | Kafka JSON schema |
| Frontend (later) | Filter + map smoke tests |

No tests that hit unauthorized scrapers. External APIs mocked.

---

## 18. Deployment

**Hackathon v0:** Docker Compose — React, FastAPI, PostgreSQL+PostGIS. Single machine.

**Later:** add Kafka (KRaft), Spark (standalone or local[*]), object storage for raw files; then cloud (managed Postgres, managed Kafka) if needed.

Secrets via environment variables. Never commit API keys.

---

## 19. Intended code layout (not created yet)

```text
apps/web/                 # React
apps/api/                 # FastAPI
ingest/adapters/          # one package per source
ingest/normalizers/
streaming/                # Kafka producers/consumers (later)
spark/                    # clean, dedupe, classify, score (later)
ml/                       # training + inference (later)
db/migrations/
infra/                    # compose / later k8s
tests/
docs/                     # this folder
```

---

## 20. Related docs

- [DATABASE_DESIGN.md](./DATABASE_DESIGN.md)
- [API_DESIGN.md](./API_DESIGN.md)
- [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)
