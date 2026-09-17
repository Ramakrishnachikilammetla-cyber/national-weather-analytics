# API design — FastAPI REST (`/api/v1`)

Contracts for the React dashboard, map, citizen reports, and admin panel. **Not implemented yet.** JSON unless noted.

**Conventions**

- Prefix: `/api/v1`
- Auth: `Authorization: Bearer <access_token>` unless marked public
- Errors: `{ "detail": "...", "code": "..." }` with standard HTTP status
- Datetimes: ISO-8601 UTC
- Pagination: `page` (1-based), `page_size` (default 20, max 100)
- List envelope: `{ "items": [], "page": 1, "page_size": 20, "total": 0 }`
- GeoJSON for map endpoints where noted
- Categories: MVP codes `rainfall`, `thunderstorms`, `flooding`, `heatwaves`, `fog`, `dust_storms`, `strong_winds`

Roles: `citizen`, `analyst`, `admin`.

---

## 1. Health (public)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/ready` | Postgres reachable |

---

## 2. Authentication

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/auth/register` | Public | Create citizen user |
| POST | `/auth/login` | Public | Email/password → JWT |
| POST | `/auth/refresh` | Refresh token | New access token (later if needed) |
| GET | `/auth/me` | Any user | Current profile + role |

**POST `/auth/login` body:** `{ "email", "password" }`  
**Response:** `{ "access_token", "token_type": "bearer", "user": { "id", "email", "display_name", "role" } }`

Admin users are **not** self-registered; seed or `POST /admin/users`.

---

## 3. Reference data (filters / map)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/categories` | Public | MVP + future flags (`mvp: true/false`) |
| GET | `/geo/states` | Public | State list for filters |
| GET | `/geo/districts` | Public | Query: `state_code` |
| GET | `/geo/states/{code}/boundary` | Public | GeoJSON MultiPolygon |
| GET | `/geo/districts/{code}/boundary` | Public | GeoJSON MultiPolygon |

---

## 4. Shared list query parameters

Used by observations, reports, events, and dashboard aggregates:

| Param | Meaning |
|-------|---------|
| `from` / `to` | Inclusive timestamptz range |
| `category` | Repeatable; MVP codes |
| `state_code` | |
| `district_code` | |
| `bbox` | `min_lon,min_lat,max_lon,max_lat` |
| `verification_status` | Human status; omit for observations (use `qc_status`) |
| `min_confidence` | Optional floor on latest `ml_scores.confidence` |
| `page` / `page_size` | |

Invalid bbox or unknown category → `400`.

---

## 5. Observations (official / dataset)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/observations` | Public or citizen | Filtered time series / table |
| GET | `/observations/{id}` | Public or citizen | Detail + QC flags |
| GET | `/stations` | Public | Query: `state_code`, `bbox` |
| GET | `/stations/{id}` | Public | Station metadata |

Writes to observations are **ingest/admin**, not the public app:

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/admin/ingest/observations/run` | Admin | Trigger adapter job for a `source_code` |

---

## 6. Citizen reports

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/reports` | Citizen+ | Submit report (claim, not verified) |
| GET | `/reports` | Public | List; default hide `rejected` for anonymous; include all for analyst+ |
| GET | `/reports/{id}` | Public | Detail; include latest ml_score if present |
| GET | `/reports/me` | Citizen+ | Caller’s submissions |

**POST `/reports` body:**

```json
{
  "category": "rainfall",
  "title": "optional",
  "description": "...",
  "occurred_at": "2026-09-17T12:00:00Z",
  "longitude": 77.2,
  "latitude": 28.6,
  "consent": true
}
```

Server sets `verification_status = pending_review`. Does **not** set true/fake from ML (ML may run async later).

---

## 7. Weather events (aggregated)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/events` | Public | Filtered events |
| GET | `/events/{id}` | Public | Event + linked reports/observations ids |
| GET | `/events/{id}/evidence` | Public | Latest ml_score + human reviews summary |

Creating/merging events is pipeline or admin (later):

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/admin/events` | Analyst+ | Optional manual event |
| PATCH | `/admin/events/{id}` | Analyst+ | Edit window/category |

---

## 8. Map

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/map/points` | Public | GeoJSON FeatureCollection of reports and/or events (query: `layer=reports|events|observations`, plus shared filters) |
| GET | `/map/choropleth` | Public | Per-district or per-state counts (query: `level=district|state`, shared filters) |

Keep payloads bounded (`page_size` or a max feature cap, e.g. 2000) for hackathon browsers.

---

## 9. Dashboard analytics

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/analytics/summary` | Public | Totals by category, pending vs confirmed counts, date window |
| GET | `/analytics/timeseries` | Public | Query: `bucket=hour|day`, `metric=reports|events|precip` |
| GET | `/analytics/top-districts` | Public | Ranked counts in window |

v0 **realtime:** clients poll these + `/map/points` on an interval. Later: §13 stream.

---

## 10. Public posts (if adapter enabled)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/public-posts` | Public | Official feed items, same filters where geo exists |
| GET | `/public-posts/{id}` | Public | Detail |

No scrape endpoint. Ingest via admin job only.

---

## 11. Moderation (analyst / admin)

Human verification only. Body includes `status` + optional `notes`. **Forbidden** to accept a client field `is_fake` as ML truth.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/admin/review-queue` | Analyst+ | `subject_type`, `verification_status=pending_review`, pagination |
| POST | `/admin/reports/{id}/review` | Analyst+ | Set human status; writes `verification_reviews` + audit |
| POST | `/admin/public-posts/{id}/review` | Analyst+ | Same |
| POST | `/admin/events/{id}/review` | Analyst+ | Same |
| GET | `/admin/reports/{id}/scores` | Analyst+ | All ml_scores (evidence JSON) |

Allowed `status`: `pending_review`, `confirmed`, `disputed`, `rejected`, `needs_more_info`.

---

## 12. Admin: users, sources, ingest, audit

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/admin/users` | Admin | List users |
| POST | `/admin/users` | Admin | Create analyst/admin (or citizen) |
| PATCH | `/admin/users/{id}` | Admin | `is_active`, `role_id` |
| GET | `/admin/sources` | Admin | List adapters |
| PATCH | `/admin/sources/{id}` | Admin | `is_enabled`, non-secret `config` |
| GET | `/admin/ingest/runs` | Admin | Job history |
| POST | `/admin/ingest/run` | Admin | `{ "source_code": "open_meteo" }` |
| GET | `/admin/audit` | Admin | Filter `action`, `from`, `to` |

---

## 13. Realtime (later phase)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/stream/events` | Citizen+ | SSE or WebSocket of new verified-or-all events (product choice) |

v0: omit; document for Kafka phase.

---

## 14. What the frontend needs (mapping)

| UI | Endpoints |
|----|-----------|
| Login / register | `/auth/*` |
| Dashboard KPIs | `/analytics/summary`, `/analytics/timeseries` |
| Filters | `/categories`, `/geo/states`, `/geo/districts` + query params |
| India map | `/map/points`, `/map/choropleth`, boundaries |
| Event/report lists | `/events`, `/reports` |
| Submit report | `POST /reports` |
| Admin queue | `/admin/review-queue`, `POST .../review` |
| Admin sources/users | `/admin/sources`, `/admin/users`, `/admin/ingest/*` |

---

## 15. Authorization matrix (summary)

| Capability | Public | Citizen | Analyst | Admin |
|------------|--------|---------|---------|-------|
| Read dashboard/map (non-rejected) | yes | yes | yes | yes |
| Submit report | | yes | yes | yes |
| Change verification_status | | | yes | yes |
| Manage users/sources/ingest | | | | yes |

---

## 16. Out of scope

- GraphQL
- Scraping or “fetch URL” proxy APIs
- Endpoints that auto-mark reports true/fake from a model
