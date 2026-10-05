# GymBeam API

FastAPI backend for the GymBeam mobile app: patterns, exercises, paired
devices, training sessions with telemetry ingestion, and analytics.

Accounts live in Supabase Auth. The app signs users up and in against
Supabase directly, then sends the Supabase access token to this API, which
verifies it against the project's public signing keys. Data lives in the
same Supabase project's Postgres database.

JSON is camelCase on the wire and matches the app's TypeScript types in
`src/types/domain.ts` and `src/types/telemetry.ts`.

## Requirements

- Python 3.12+
- A Supabase project (auth, and Postgres for staging/production)
- SQLite works for local development without touching the hosted database

## Getting started

```bash
cd backend
make install
cp .env.example .env
make migrate
make dev
```

After that first setup, `make dev` is all you need each time. The `make`
targets call the virtualenv's Python directly, so there is no need to
activate it first.

The API is then at http://localhost:8000, with interactive docs at
http://localhost:8000/docs.

To reach it from a phone on the same Wi-Fi, bind to all interfaces and use
your computer's LAN IP:

```bash
make dev-lan
```

## Commands

| Command | Purpose |
| --- | --- |
| `make dev` | Run with auto-reload |
| `make dev-lan` | Same, reachable from phones and emulators on the network |
| `make start` | Run in production mode |
| `make test` | Run the tests (in-memory SQLite) |
| `make lint` | Lint and format |
| `make migrate` | Apply migrations |
| `make install` | Create the virtualenv and install dependencies |
| `.venv/bin/python -m alembic revision --autogenerate -m "..."` | Create a migration after changing `app/models.py` |

The targets are defined in the `Makefile`.

## Configuration

Set in `.env` or the process environment. See `.env.example`.

| Variable | Default | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `development`, `staging` or `production` |
| `DATABASE_URL` | `sqlite:///./gymbeam.db` | Supabase connection string (Project Settings > Database). Any of the direct, session pooler or transaction pooler URLs works. |
| `SUPABASE_URL` | required | `https://<project-ref>.supabase.co` |
| `SUPABASE_JWKS_URL` | derived from `SUPABASE_URL` | Where the token signing keys are fetched from |
| `CORS_ORIGINS` | `[]` | JSON list. Only needed for Expo web; native apps don't use CORS. |

## Endpoints

Everything is under `/api/v1` and needs
`Authorization: Bearer <Supabase access token>`. Every resource is private to
the user who created it.

| Method | Path | |
| --- | --- | --- |
| GET | `/auth/me` | Current user. The first authenticated call creates the user's local profile from the token. |
| GET, POST | `/patterns` | |
| GET, PUT, DELETE | `/patterns/{id}` | Delete returns 409 while an exercise uses the pattern |
| GET, POST | `/exercises` | `?favorite=true` filters the list |
| GET, PATCH, DELETE | `/exercises/{id}` | |
| GET, POST | `/devices` | POST pairs a device; the same MAC address again updates it |
| PUT | `/devices/{id}/metrics` | Latest CPU/memory/disk/temperature snapshot |
| DELETE | `/devices/{id}` | Unpair |
| GET, POST | `/sessions` | |
| GET, DELETE | `/sessions/{id}` | |
| POST | `/sessions/{id}/events` | Array of 1–500 `TelemetryEvent`s |
| GET | `/sessions/{id}/events` | |
| GET | `/sessions/{id}/metrics` | Targets attempted/completed/missed and target times |
| GET | `/analytics/summary` | Totals across sessions, optional `?from=&to=` |
| GET | `/health` | Outside `/api/v1`, no auth |

List endpoints take `limit` (max 200) and `offset`.

### Auth from the app

Sign-up, login, token refresh, logout and password reset are Supabase's, not
this API's. In the app, use `supabase-js` with the publishable key, pass the
user's name as `options.data.full_name` on sign-up, and send
`session.access_token` as the bearer token here. The secret key is not used
by this backend and must never go in the app.

### Database access

The initial migration turns on row level security for every table with no
policies. Supabase exposes the `public` schema over its own REST API, so
without this anyone holding the publishable key could read these tables
directly. With it, only this backend's database connection can.

### Sessions and telemetry

1. `POST /sessions` when a drill starts. Use the returned `id` for everything
   that follows; the `sessionId` inside each event is the device's own id and
   is ignored.
2. `POST /sessions/{id}/events` with events as they arrive, or in one batch
   afterwards. Events are deduplicated by `eventId`, so retrying a batch after
   a dropped connection is safe.
3. The session's `state` follows the events: `SESSION_COMPLETED` →
   `completed`, `SESSION_STOPPED` → `stopped`, `ERROR` → `error`.

Target times come from `metrics.reactionTimeMs` on `TARGET_REACHED` events.

## Layout

```
app/
  main.py        app and router wiring
  config.py      settings from the environment
  db.py          engine and session
  models.py      SQLAlchemy tables
  schemas.py     request and response shapes
  security.py    Supabase token verification
  deps.py        current user and ownership helpers
  stats.py       target aggregates shared by sessions and analytics
  routers/       one file per resource
migrations/      Alembic
tests/
```

## Not built yet

- `POST /ai/coach` from the original contract sketch.
- `estimatedCaloriesBurned` is always `null`; there is no data to derive it from.
