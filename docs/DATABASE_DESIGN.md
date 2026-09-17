# Database design — PostgreSQL / PostGIS

Logical schema for the National Weather Big Data Analytics Platform (India). This is a **design**, not a migration. Types are PostgreSQL.

**Conventions**

- Primary keys: `UUID` (`gen_random_uuid()`) unless noted.
- Timestamps: `TIMESTAMPTZ` stored in UTC; UI displays IST.
- Coordinates: `GEOGRAPHY(POINT, 4326)` unless stated.
- Category codes: MVP enum values listed below; extra values allowed later via check extension or lookup table.

---

## 1. Category lookup (MVP)

Table `event_categories` is the source of truth (preferred over a brittle DB enum so future codes can be inserted).

| code (PK) | label | mvp |
|-----------|--------|-----|
| rainfall | Rainfall | true |
| thunderstorms | Thunderstorms | true |
| flooding | Flooding | true |
| heatwaves | Heatwaves | true |
| fog | Fog | true |
| dust_storms | Dust storms | true |
| strong_winds | Strong winds | true |
| cyclone | Cyclone | false (future) |
| hail | Hail | false (future) |
| drought_related | Drought-related | false (future) |
| other | Other | false (future) |

`weather_events.primary_category` and `citizen_reports.category` **FK** → `event_categories.code`.

---

## 2. Entity-relationship overview

```text
roles 1───< users
users 1───< citizen_reports
users 1───< verification_reviews
users 1───< audit_log

weather_sources 1───< stations
weather_sources 1───< observations
weather_sources 1───< public_posts
weather_sources 1───< ingest_runs

india_states 1───< india_districts
india_districts 1───< stations (optional)
india_districts 1───< citizen_reports (optional, derived)

stations 1───< observations

citizen_reports 1───< ml_scores
public_posts 1───< ml_scores
weather_events 1───< ml_scores
citizen_reports 1───< verification_reviews
public_posts 1───< verification_reviews
weather_events 1───< event_observations (M:N observations)
weather_events 1───< event_reports (M:N reports)
```

---

## 3. Auth and access

### `roles`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `name` | TEXT UNIQUE NOT NULL | `citizen`, `analyst`, `admin` |
| `created_at` | TIMESTAMPTZ NOT NULL | |

### `users`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `email` | CITEXT UNIQUE NOT NULL | |
| `password_hash` | TEXT NOT NULL | |
| `display_name` | TEXT | |
| `role_id` | UUID NOT NULL FK → roles.id | |
| `is_active` | BOOLEAN NOT NULL DEFAULT true | |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

---

## 4. India geography

Load from an **open or official** boundary dataset when implementing. Do not invent polygons.

### `india_states`

| Column | Type | Notes |
|--------|------|--------|
| `code` | TEXT PK | e.g. `MH`, `KA` (document coding scheme in ingest) |
| `name` | TEXT NOT NULL | |
| `geom` | GEOMETRY(MULTIPOLYGON, 4326) | GIST index |

### `india_districts`

| Column | Type | Notes |
|--------|------|--------|
| `code` | TEXT PK | Unique district code |
| `state_code` | TEXT NOT NULL FK → india_states.code | |
| `name` | TEXT NOT NULL | |
| `geom` | GEOMETRY(MULTIPOLYGON, 4326) | GIST index |

Point-in-polygon at ingest (or a trigger) may fill `state_code` / `district_code` on reports and observations.

---

## 5. Sources, stations, observations

### `weather_sources`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `code` | TEXT UNIQUE NOT NULL | e.g. `open_meteo`, `imd_ogd`, `citizen_app`, `ndma_official_rss` |
| `name` | TEXT NOT NULL | |
| `kind` | TEXT NOT NULL | `api`, `dataset`, `public_feed`, `citizen` |
| `license_note` | TEXT | Attribution / terms |
| `base_url` | TEXT | If applicable |
| `is_enabled` | BOOLEAN NOT NULL DEFAULT true | Admin toggle |
| `config` | JSONB | Rate limits, dataset ids — no secrets in DB if avoidable |
| `created_at` | TIMESTAMPTZ NOT NULL | |

### `stations`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `source_id` | UUID NOT NULL FK → weather_sources.id | |
| `external_id` | TEXT NOT NULL | ID in the upstream system |
| `name` | TEXT | |
| `location` | GEOGRAPHY(POINT, 4326) NOT NULL | |
| `state_code` | TEXT FK → india_states.code | nullable until joined |
| `district_code` | TEXT FK → india_districts.code | nullable |
| `elevation_m` | NUMERIC | |
| `is_active` | BOOLEAN NOT NULL DEFAULT true | |
| UNIQUE (`source_id`, `external_id`) | | |

### `observations`

Measured or forecast samples. **QC workflow only** (not citizen verification).

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `source_id` | UUID NOT NULL FK → weather_sources.id | |
| `station_id` | UUID FK → stations.id | nullable for grid cells |
| `external_id` | TEXT | Upstream observation id if any |
| `observed_at` | TIMESTAMPTZ NOT NULL | |
| `location` | GEOGRAPHY(POINT, 4326) NOT NULL | |
| `state_code` | TEXT FK | |
| `district_code` | TEXT FK | |
| `temperature_c` | NUMERIC | |
| `precipitation_mm` | NUMERIC | Period documented in `variables` or `period_hours` |
| `wind_speed_ms` | NUMERIC | |
| `wind_gust_ms` | NUMERIC | |
| `visibility_m` | NUMERIC | fog-related |
| `humidity_pct` | NUMERIC | |
| `variables` | JSONB | Extra official fields |
| `period_hours` | NUMERIC | e.g. 1 = hourly rain |
| `qc_status` | TEXT NOT NULL DEFAULT `pending` | `pending`, `passed`, `flagged`, `rejected` |
| `qc_flags` | TEXT[] | e.g. `out_of_range`, `outside_india` |
| `raw_payload` | JSONB | If licence allows |
| `ingested_at` | TIMESTAMPTZ NOT NULL | |
| UNIQUE (`source_id`, `station_id`, `observed_at`, `period_hours`) | | Dedup key when station present |

Indexes: `(observed_at)`, GIST `(location)`, `(state_code, observed_at)`, `(qc_status)`.

---

## 6. Citizen reports and public posts

### `citizen_reports`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id | nullable if anonymous allowed (MVP: prefer logged-in) |
| `source_id` | UUID NOT NULL FK → weather_sources.id | citizen adapter |
| `category` | TEXT NOT NULL FK → event_categories.code | MVP seven in product UI |
| `title` | TEXT | |
| `description` | TEXT | |
| `occurred_at` | TIMESTAMPTZ NOT NULL | User-stated time |
| `location` | GEOGRAPHY(POINT, 4326) NOT NULL | |
| `state_code` | TEXT FK | |
| `district_code` | TEXT FK | |
| `media_refs` | JSONB | Object storage keys later; empty in early MVP |
| `consent_at` | TIMESTAMPTZ | Submission consent |
| `duplicate_of_id` | UUID FK → citizen_reports.id | Self-FK; null if canonical |
| `verification_status` | TEXT NOT NULL DEFAULT `pending_review` | See §8 |
| `ingested_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

Indexes: GIST `(location)`, `(occurred_at)`, `(category)`, `(verification_status)`.

### `public_posts`

Permitted official feeds only.

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `source_id` | UUID NOT NULL FK → weather_sources.id | |
| `external_id` | TEXT NOT NULL | Platform post id |
| `permalink` | TEXT | |
| `posted_at` | TIMESTAMPTZ | |
| `fetched_at` | TIMESTAMPTZ NOT NULL | |
| `text_body` | TEXT | |
| `location` | GEOGRAPHY(POINT, 4326) | If provided |
| `state_code` | TEXT FK | |
| `district_code` | TEXT FK | |
| `suggested_category` | TEXT FK → event_categories.code | From classifier |
| `verification_status` | TEXT NOT NULL DEFAULT `pending_review` | |
| `raw_payload` | JSONB | If ToS allows |
| UNIQUE (`source_id`, `external_id`) | | |

---

## 7. Derived weather events

Aggregated incidents for the dashboard (optional in earliest MVP: UI can list reports + observations until this is filled).

### `weather_events`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `primary_category` | TEXT NOT NULL FK → event_categories.code | |
| `secondary_categories` | TEXT[] | Future tags |
| `title` | TEXT | |
| `started_at` | TIMESTAMPTZ NOT NULL | |
| `ended_at` | TIMESTAMPTZ | |
| `centroid` | GEOGRAPHY(POINT, 4326) | |
| `area` | GEOGRAPHY(POLYGON, 4326) | Optional |
| `state_code` | TEXT FK | |
| `district_code` | TEXT FK | |
| `severity` | TEXT | e.g. `unknown`, `advisory`, `warning` — only if sourced, not invented |
| `verification_status` | TEXT NOT NULL DEFAULT `pending_review` | Human |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

### `event_observations` (M:N)

| Column | Type | Notes |
|--------|------|--------|
| `event_id` | UUID PK FK → weather_events.id | Composite PK |
| `observation_id` | UUID PK FK → observations.id | |

### `event_reports` (M:N)

| Column | Type | Notes |
|--------|------|--------|
| `event_id` | UUID PK FK → weather_events.id | |
| `report_id` | UUID PK FK → citizen_reports.id | |

---

## 8. Verification (human) and ML scores (signal)

Human status is **separate** from ML. Allowed `verification_status` values:

`pending_review` | `confirmed` | `disputed` | `rejected` | `needs_more_info`

ML **must not** write these automatically.

### `ml_scores`

Polymorphic score rows (one model version per subject).

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `subject_type` | TEXT NOT NULL | `citizen_report`, `public_post`, `weather_event` |
| `subject_id` | UUID NOT NULL | |
| `model_version` | TEXT NOT NULL | |
| `confidence` | NUMERIC NOT NULL CHECK (0–1) | Evidence strength, not truth |
| `evidence` | JSONB NOT NULL DEFAULT `{}` | Corroborating facts |
| `scored_at` | TIMESTAMPTZ NOT NULL | |
| UNIQUE (`subject_type`, `subject_id`, `model_version`) | | |

### `verification_reviews`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `subject_type` | TEXT NOT NULL | same as above |
| `subject_id` | UUID NOT NULL | |
| `reviewer_id` | UUID NOT NULL FK → users.id | analyst/admin |
| `status` | TEXT NOT NULL | copies allowed statuses |
| `notes` | TEXT | |
| `created_at` | TIMESTAMPTZ NOT NULL | |

Application layer copies the latest review onto `verification_status` of the subject row.

---

## 9. Ingest operations and audit

### `ingest_runs`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `source_id` | UUID NOT NULL FK → weather_sources.id | |
| `started_at` | TIMESTAMPTZ NOT NULL | |
| `finished_at` | TIMESTAMPTZ | |
| `status` | TEXT NOT NULL | `running`, `success`, `failed` |
| `records_in` | INTEGER | |
| `records_written` | INTEGER | |
| `error_summary` | TEXT | |
| `triggered_by` | TEXT | `scheduler`, `admin`, `kafka` |

### `audit_log`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id | |
| `action` | TEXT NOT NULL | e.g. `report.moderate`, `source.disable` |
| `entity_type` | TEXT | |
| `entity_id` | UUID | |
| `payload` | JSONB | |
| `created_at` | TIMESTAMPTZ NOT NULL | |

---

## 10. Relationship summary

| From | To | Type | On delete (suggested) |
|------|----|------|------------------------|
| users.role_id | roles.id | N:1 | Restrict |
| stations.source_id | weather_sources.id | N:1 | Restrict |
| observations.source_id | weather_sources.id | N:1 | Restrict |
| observations.station_id | stations.id | N:1 | Set null |
| citizen_reports.user_id | users.id | N:1 | Set null |
| citizen_reports.category | event_categories.code | N:1 | Restrict |
| citizen_reports.duplicate_of_id | citizen_reports.id | N:1 | Set null |
| public_posts.source_id | weather_sources.id | N:1 | Restrict |
| weather_events.primary_category | event_categories.code | N:1 | Restrict |
| event_observations | events + observations | M:N | Cascade from event |
| event_reports | events + reports | M:N | Cascade from event |
| india_districts.state_code | india_states.code | N:1 | Restrict |
| verification_reviews.reviewer_id | users.id | N:1 | Restrict |
| ingest_runs.source_id | weather_sources.id | N:1 | Cascade |

---

## 11. Filter-oriented indexes (dashboard)

- `observations (observed_at DESC)` + GIST location  
- `citizen_reports (occurred_at DESC, category, verification_status)`  
- `weather_events (started_at DESC, primary_category, verification_status)`  
- Partial index on `verification_status = 'pending_review'` for the admin queue  

---

## 12. Out of scope for v0 schema (document only)

- Full media blob tables (use `media_refs` JSON until object storage exists).
- Kafka offset tables (when Kafka is added).
- ML training datasets (export jobs later).
