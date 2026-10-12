# Event Ticketing Service

A REST API for event ticket booking. FastAPI and MySQL, with JWT authentication,
role-based access control, and concurrency-safe ticket allocation that provably
cannot oversell an event.

[![CI](https://github.com/AayushKaushik07/event-ticketing-service/actions/workflows/ci.yml/badge.svg)](https://github.com/AayushKaushik07/event-ticketing-service/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Contents

- [What it does](#what-it-does)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Local development setup](#local-development-setup)
- [API reference](#api-reference)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Database schema](#database-schema)
- [Design decisions](#design-decisions)
- [Concurrency: preventing oversold tickets](#concurrency-preventing-oversold-tickets)
- [Testing](#testing)
- [Database migrations](#database-migrations)
- [Continuous integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)

---

## What it does

- **Admins** create and delete events, and view booking counts.
- **Users** register, log in, book tickets, and view their own bookings.
- **Nobody** can oversell an event, including under concurrent load.

Authentication is JWT bearer tokens. Authorization is a `role` column on the
user, enforced by FastAPI dependencies at the route level. A caller's identity
is taken from the validated token and never from the request body.

## Tech stack

| Layer | Choice |
|---|---|
| API framework | FastAPI 0.115 (Python 3.12) |
| Database | MySQL 8.0 (InnoDB) |
| ORM / queries | SQLAlchemy 2.0, typed `Mapped[...]` models |
| Schema versioning | Alembic |
| Auth | PyJWT (HS256), bcrypt password hashing |
| Validation | Pydantic v2 |
| Tests | pytest, run against real MySQL |
| Container | Multi-stage Dockerfile, non-root, Docker Compose |
| CI | GitHub Actions with a MySQL service container |
| Lint | Ruff |

---

## Quick start

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop) (or
Docker Engine) and nothing else — MySQL runs in a container, so you do not need
it installed locally.

```bash
git clone https://github.com/AayushKaushik07/event-ticketing-service.git
cd event-ticketing-service

cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into JWT_SECRET

docker compose up --build
```

Compose reads `JWT_SECRET` from `.env`. Without one it falls back to a dev-only
secret, which is fine for trying the API locally and never acceptable anywhere else.

MySQL takes 20–30 seconds to initialise on first run; the API waits for its
healthcheck before starting. Then create the first admin:

```bash
docker compose exec -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD='changeme123' \
  api python -m scripts.seed_admin
```

Open **http://localhost:8000/docs**, click **Authorize**, log in as the admin,
and every protected endpoint becomes callable from the browser.

Stop with `docker compose down`, or `docker compose down -v` to also drop the
database volume.

---

## Local development setup

For day-to-day work, run MySQL in a container and the API on your machine so you
get hot reload.

### 1. Dependencies

```bash
python -m venv venv
source venv/bin/activate          # Linux/macOS
venv\Scripts\Activate.ps1         # Windows PowerShell

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Environment

```bash
cp .env.example .env              # Copy-Item .env.example .env  on Windows
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the result into `JWT_SECRET` in `.env`. That value signs every token —
anyone holding it can forge credentials for any account, which is why `.env` is
gitignored and only `.env.example` is committed.

### 3. Database and schema

```bash
docker compose up -d db           # wait for STATUS = healthy in `docker compose ps`
alembic upgrade head
```

### 4. First admin

```bash
# Linux/macOS
ADMIN_USERNAME=admin ADMIN_PASSWORD='changeme123' python -m scripts.seed_admin
```

```powershell
# Windows PowerShell
$env:ADMIN_USERNAME="admin"; $env:ADMIN_PASSWORD="changeme123"
python -m scripts.seed_admin
```

The script is idempotent — running it twice leaves the existing admin alone.

### 5. Run

```bash
uvicorn app.main:app --reload
```

### Daily loop

```bash
docker compose up -d db
uvicorn app.main:app --reload
```

### Windows notes

Two things bite on Windows specifically:

**Environment variables.** PowerShell has no `VAR=value command` prefix syntax.
Use `$env:VAR="value"` on its own line first. These persist for the whole
session, so clear them (`Remove-Item Env:DATABASE_URL`) or use a separate
terminal for tests — otherwise a later command silently targets the test
database.

**Smart App Control / WDAC** may block pip-installed console scripts
(`alembic.exe`, `pytest.exe`, `uvicorn.exe`), reporting
`An Application Control policy has blocked this file`. Invoke the modules
directly instead — identical code, no wrapper executable:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
python -m pytest -v
python -m ruff check app tests scripts
```

This affects only the Windows host. Containers and CI runners are unaffected.

---

## API reference

| Method | Path | Access | Success | Errors |
|---|---|---|---|---|
| `POST` | `/auth/register` | public | 201 | 409 username taken, 422 invalid |
| `POST` | `/auth/login` | public | 200 | 401 bad credentials |
| `GET` | `/auth/me` | authenticated | 200 | 401 |
| `GET` | `/events` | public | 200 | — |
| `POST` | `/events` | **admin** | 201 | 401, 403, 422 past date or bad capacity |
| `DELETE` | `/events/{id}` | **admin** | 204 | 401, 403, 404 |
| `POST` | `/tickets` | authenticated | 201 | 401, 404 no such event, 400 sold out |
| `GET` | `/tickets/me` | authenticated | 200 | 401 |
| `GET` | `/tickets/count?event_id=N` | **admin** | 200 | 401, 403, 404 |
| `GET` | `/health` | public | 200 | 503 database unreachable |

Interactive documentation is generated at `/docs` (Swagger UI) and `/redoc`.

### Examples

Register and log in:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice", "password": "password123"}'

curl -X POST http://localhost:8000/auth/login \
  -d 'username=alice&password=password123'
# {"access_token":"eyJhbGciOi...","token_type":"bearer"}
```

Login is form-encoded rather than JSON so that Swagger UI's **Authorize**
button works directly against it.

Create an event (admin token required):

```bash
curl -X POST http://localhost:8000/events \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name": "Konzert", "available_tickets": 100, "event_date": "2027-06-01T19:30:00Z"}'
```

```json
{
  "id": 1,
  "name": "Konzert",
  "available_tickets": 100,
  "total_capacity": 100,
  "event_date": "2027-06-01T19:30:00",
  "created_at": "2026-09-02T09:15:04"
}
```

Book a ticket — note there is no `user_id` in the body:

```bash
curl -X POST http://localhost:8000/tickets \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"event_id": 1}'
```

---

## Configuration

All configuration is read from the environment via `pydantic-settings`. Nothing
environment-dependent is hardcoded, so the same image runs locally, in CI, and
in a deployment with only the environment changing.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | yes | — | e.g. `mysql+pymysql://user:pass@host:3306/db` |
| `JWT_SECRET` | yes | — | HMAC signing key; generate with `secrets.token_hex(32)` |
| `JWT_ALGORITHM` | no | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `60` | Token lifetime |
| `APP_ENV` | no | `local` | Informational label |

The driver prefix matters: `mysql+pymysql://`, not `mysql://`. The bare scheme
resolves to `MySQLdb`, which is not installed.

---

## Project structure

```
app/
├── main.py              FastAPI app, routers, exception handlers, /health
├── config.py            environment-backed settings
├── db.py                engine, session factory, get_db dependency
├── models.py            SQLAlchemy ORM models
├── errors.py            domain exceptions
├── security.py          bcrypt hashing, JWT encode/decode
├── dependencies.py      get_current_user, require_admin
├── repository.py        all database queries (never commits)
├── auth/                controller, service, schemas
├── events/              controller, service, schemas
└── tickets/             controller, service, schemas

alembic/versions/        migration history
scripts/seed_admin.py    creates the first admin, out of band
tests/                   integration and concurrency tests
```

Each feature package holds a controller (HTTP), a service (business logic and
transaction boundaries), and Pydantic schemas (the API contract). Shared
infrastructure sits at the top level.

---

## Database schema

```
users                              events                                bookings
─────                              ──────                                ────────
id            BIGINT PK AI         id                BIGINT PK AI        id         BIGINT PK AI
username      VARCHAR(50) UNIQUE   name              VARCHAR(200)        event_id   FK → events.id  CASCADE
password_hash VARCHAR(255)         available_tickets INT                 user_id    FK → users.id   CASCADE
role          ENUM(admin,user)     total_capacity    INT                 created_at DATETIME
created_at    DATETIME             event_date        DATETIME
                                   created_by        FK → users.id  SET NULL
                                   created_at        DATETIME

                                   CHECK (available_tickets >= 0)
                                   CHECK (available_tickets <= total_capacity)
```

Deleting an event removes its bookings by `ON DELETE CASCADE`, enforced by the
database rather than by application code, so the invariant holds even for rows
touched outside the API.

No indexes are declared by hand on `bookings.event_id` or `bookings.user_id`:
InnoDB creates an index on every foreign key column automatically, and both of
this service's lookups are on foreign keys. Declaring them would duplicate.

Primary keys are `BIGINT AUTO_INCREMENT` rather than UUIDs. InnoDB clusters
table storage on the primary key, so random UUIDs scatter inserts across pages
and fragment the index. The trade-off — enumerable ids — is acceptable here; a
separate public slug would be the fix if it were not.

---

## Design decisions

### One users table, not two

Admins and users share one table, separated by a `role` column. Separate tables
would make `bookings.user_id` ambiguous — a foreign key can only reference one
table, so an admin booking a ticket would break the constraint — and would
duplicate the login path. A third role is now an enum value, not a new table.

### Identity comes from the token

`user_id` is not accepted in the booking request body. An earlier version
accepted it, which meant any caller could book tickets in another user's name by
editing one field. Bookings are now created for whoever the validated token
identifies.

Registration has no `role` field either. If a client could supply one, privilege
escalation would be a single JSON key. Admins are created by
`scripts/seed_admin.py`, out of band.

### Login does not distinguish failure modes

An unknown username and a wrong password return the identical 401 body.
Different responses would turn the endpoint into a user-enumeration oracle.

### Layering, and where transactions begin

```
HTTP → controller → service → repository → MySQL
       status codes  business    queries only,
                     logic +     never commits
                     transaction
                     boundary
```

The repository never commits. Only the service knows where a unit of work starts
and ends, and a repository that committed mid-booking would release the row lock
early and reintroduce the exact bug the lock exists to prevent. Nothing below the
controller imports `fastapi`, which is what lets the concurrency tests drive the
service directly with no web server running.

### Deletes return 404, not 204

Deleting an unknown event returns 404 rather than succeeding silently. This is an
admin-only operation, and telling an admin the thing they tried to delete does
not exist is more useful than a misleading success. The idempotent alternative is
defensible; this is a deliberate choice.

---

## Concurrency: preventing oversold tickets

Booking is a read-check-write sequence: read remaining tickets, verify one is
available, decrement, insert a booking row. Between the read and the write,
another request can read the same value — a lost update, and the event oversells.

The fix is an exclusive row lock held for the whole transaction:

```python
event = db.execute(
    select(Event).where(Event.id == event_id).with_for_update()
).scalar_one_or_none()
```

```mermaid
sequenceDiagram
    participant A as Request A
    participant DB as MySQL (event row)
    participant B as Request B
    A->>DB: SELECT ... FOR UPDATE (lock acquired)
    B->>DB: SELECT ... FOR UPDATE (blocks)
    A->>DB: reads available_tickets = 1
    A->>DB: UPDATE to 0, INSERT booking
    A->>DB: COMMIT (lock released)
    DB-->>B: lock granted
    B->>DB: reads available_tickets = 0
    B-->>B: raises NoTicketsAvailableError → 400
```

Requests for *different* events never contend, because the lock is scoped to one
row.

### Why not a process-level lock

An earlier version used `threading.Lock`. That was correct for a single-process,
in-memory implementation and wrong beyond it in two ways: it serialised bookings
across all events, so a booking for one event blocked every other event for no
reason; and it stopped working entirely with a second worker process, because two
processes do not share a Python lock object. Moving the mutual exclusion into the
database puts it in the one place every replica can see.

### Why the CHECK constraint does not save you

`CHECK (available_tickets >= 0)` does **not** prevent overselling. Under a lost
update, every concurrent transaction reads `3` and writes `2` — the column never
goes negative, so the constraint never fires while the event is oversold. This
was confirmed by running the concurrency suite with the lock removed. The
constraint validates the value a statement writes; it cannot see that the value
was computed from a stale read. It is a backstop against a bad manual `UPDATE`,
nothing more.

### The alternative

A single atomic statement would also work:

```sql
UPDATE events SET available_tickets = available_tickets - 1
WHERE id = ? AND available_tickets > 0;
```

Zero rows affected means sold out. No explicit lock, one round trip. It was not
used here because the current form keeps the availability check and the resulting
error in one readable place, but it is the better choice under heavy contention.

---

## Testing

25 tests, run against **real MySQL rather than SQLite**. Three behaviours under
test do not exist in SQLite as configured by default: `FOR UPDATE` semantics,
`ON DELETE CASCADE` (SQLite ships with foreign key enforcement off), and CHECK
enforcement. A SQLite suite would pass green while both the locking and the
cascade were broken.

Create the test database once:

```bash
docker compose exec db mysql -uroot -prootpass -e \
  "CREATE DATABASE IF NOT EXISTS ticketing_test CHARACTER SET utf8mb4; \
   GRANT ALL ON ticketing_test.* TO 'ticketing'@'%'; FLUSH PRIVILEGES;"
```

Run:

```bash
DATABASE_URL='mysql+pymysql://ticketing:ticketing@localhost:3306/ticketing_test' \
JWT_SECRET=test pytest -v
```

```powershell
$env:DATABASE_URL="mysql+pymysql://ticketing:ticketing@localhost:3306/ticketing_test"
$env:JWT_SECRET="test"
python -m pytest -v
```

A dedicated database is used because the fixtures truncate every table between
tests.

### The concurrency tests

`tests/test_concurrency.py` synchronises ten threads on a `threading.Barrier` and
monkeypatches a delay between the availability read and the write, then asserts a
one-ticket event sells exactly one ticket.

Both of those are necessary. **A naive version of this test — spawn threads, call
the endpoint, assert one wins — passes even with the lock removed**, because each
booking completes in under a millisecond and the threads never actually overlap.
A concurrency test that cannot fail against broken code is worse than no test.

To see it work, delete `.with_for_update()` from `get_event_for_update` in
`app/repository.py` and re-run:

```
assert 10 == 1
  where 10 = ['booked', 'booked', 'booked', ...].count('booked')
```

Ten threads, one ticket, ten bookings. Restore the lock and all three pass.

---

## Database migrations

Schema changes are versioned with Alembic. The applied revision is recorded in an
`alembic_version` table inside the database itself, which is what makes
`alembic upgrade head` safe to run repeatedly and on a fresh database alike.

```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "description"  # after editing app/models.py
alembic downgrade -1                              # undo the last one
```

**Read every autogenerated migration before applying it.** Autogenerate produces
a draft, not an authority: it reliably misses CHECK constraints, server-side
defaults, and MySQL `ENUM` changes.

The container runs `alembic upgrade head` in its `CMD` before starting the
server. See [Known limitations](#known-limitations) for why that would not scale.

---

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:

1. **Lint** — `ruff check app tests scripts`
2. **Test** — `pytest` against a MySQL 8 service container
3. **Build and publish** — multi-stage image to GHCR, tagged `latest` and the
   commit SHA

The publish job declares `needs: test`, so an image is only built from a commit
whose tests passed.

The image runs as a non-root user, and dependencies are installed in a builder
stage so the compiler toolchain never reaches the runtime layer.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `cannot connect to the Docker daemon` | Docker Desktop not running | Start it; wait for "Engine running" |
| `Bind for 0.0.0.0:3306 failed` | Local MySQL occupying the port | Map `"3307:3306"` in compose, update `DATABASE_URL` |
| `No module named 'MySQLdb'` | URL uses `mysql://` | Use `mysql+pymysql://` |
| `RSA public key is not available client side` | MySQL 8 `caching_sha2_password` | `pip install cryptography` (already in requirements) |
| `Can't connect to MySQL server on 'db'` | API started before MySQL was ready | `depends_on: condition: service_healthy` in compose |
| Alembic generates an empty migration | `import app.models` missing from `alembic/env.py` | Restore it — autogenerate reads registered metadata, it does not scan files |
| `Cannot truncate a table referenced in a foreign key constraint` | Cleanup outside the fixtures | The `SET FOREIGN_KEY_CHECKS` wrapper in `conftest.py` handles it |
| `MySQL server has gone away` after idle | Connection timed out | Handled by `pool_pre_ping` and `pool_recycle` in `db.py` |
| `An Application Control policy has blocked this file` | Windows blocking pip console scripts | Use `python -m alembic`, `python -m pytest`, `python -m uvicorn` |
| `'VAR=value' is not recognized` | bash syntax in PowerShell | `$env:VAR="value"` on its own line |
| `exec /bin/sh: no such file or directory` in the container | CRLF line endings in the image | `.gitattributes` enforces LF; `git add --renormalize .` and rebuild |
| 403 on an endpoint you expect to work | Logged in as the wrong role | Re-authorize as admin |

---

## Known limitations

Deliberate trade-offs, documented rather than hidden:

- **Migrations run in the container's `CMD`.** With multiple replicas every
  container races to migrate on startup. Alembic takes a lock so it usually
  survives, but the correct pattern is a separate migration job or init container
  that runs once before new application containers start.
- **`available_tickets` is a denormalised counter** alongside the booking rows.
  It gives O(1) availability checks but can drift if any code path ever inserts a
  booking outside `book_ticket`. A test asserts the two agree.
- **No idempotency keys.** A client retrying after a network timeout can book
  twice. A client-supplied key with a unique constraint would fix it.
- **No refresh tokens.** Access tokens expire after 60 minutes and the user logs
  in again — fine at this scope, irritating in a real client.
- **No rate limiting on `/auth/login`**, so the endpoint is open to online
  password guessing. Production would need throttling or lockout.
- **Users may book the same event repeatedly.** Intentional, since one person
  buying several tickets is normal. Adding
  `UniqueConstraint("event_id", "user_id")` and catching `IntegrityError` would
  restrict it, and would do so at the database level rather than with a racy
  check-then-insert.

---

## License

MIT — see [LICENSE](LICENSE).
