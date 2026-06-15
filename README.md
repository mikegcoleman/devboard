# DevBoard

A developer issue and project tracker — full-stack demo app used to practice pointing AI coding agents at real bugs.

**Stack**: FastAPI + SQLAlchemy + PostgreSQL (backend) · Next.js 14 App Router + Tailwind CSS (frontend) · Docker Compose

---

## Quick start

```bash
docker compose up --build
```

- API + Swagger UI: http://localhost:8000/docs
- Frontend: http://localhost:3000

### Run backend tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## Known bugs and unfinished features

This codebase contains **five intentional defects** — a mix of bugs with failing tests and unimplemented stubs. They're designed as exercises for AI coding agents: point an agent at this repo, ask it to find and fix the issues, and review the resulting PRs.

---

### Bug 1 — Pagination off-by-one

**File**: `backend/app/routers/issues.py`, line 72  
**Tests that fail**: `test_pagination_first_page_returns_results`, `test_pagination_second_page`

`list_issues` computes the SQL `OFFSET` as `page * page_size` instead of `(page - 1) * page_size`. This means page 1 always skips the first `page_size` rows — users never see the first page of results.

```python
# current (wrong)
skip = page * page_size

# should be
skip = (page - 1) * page_size
```

---

### Bug 2 — `updated_at` never updates

**File**: `backend/app/models.py`, lines 57 and 76  
**Models affected**: `Project`, `Issue`

Both `updated_at` columns are defined with `default=datetime.utcnow` but no `onupdate` hook. SQLAlchemy only calls `default` on INSERT; without `onupdate`, the column stays frozen at the row's creation time no matter how many times the record is updated.

```python
# current (wrong) — on both Project and Issue
updated_at = Column(DateTime, default=datetime.utcnow)

# should be
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

### Bug 3 — Missing authorization on issue update

**File**: `backend/app/routers/issues.py`, lines 141–183

`update_issue` checks that the caller owns the *project*, but not that they are the reporter or assignee of the specific *issue*. Any project member can edit any issue in the project — change the title, reassign it, close it — regardless of whether they created or were assigned to it.

The fix is to add an authorization check after fetching the issue:

```python
if issue.reporter_id != current_user.id and issue.assignee_id != current_user.id:
    raise HTTPException(status_code=403, detail="Not authorized to edit this issue")
```

---

### Bug 4 — Search endpoint not implemented

**File**: `backend/app/routers/issues.py`, lines 81–114

`GET /projects/{id}/issues/search?q=<query>` always returns `501 Not Implemented`. The route exists and is wired up, but the query logic is missing. The endpoint should return all issues in the project where the title or description contains the search string (case-insensitive).

A commented-out skeleton of the correct implementation is already in the file — it just needs to be uncommented and the `raise HTTPException(status_code=501, ...)` line removed.

---

### Bug 5 — Email notifications are stubs

**File**: `backend/app/services/notifications.py`

`send_status_change_notification()` is called by `update_issue` whenever an issue status changes, but the function only logs to stdout — it never sends an email. The module docstring describes what a real implementation needs:

1. Load SMTP settings from config (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`)
2. Render an HTML message with the status change details
3. Send via `aiosmtplib` (async, to match the `async def` signature)

A commented-out skeleton using `aiosmtplib` is already in the file.

---

## Project structure

```
devboard/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router registration
│   │   ├── models.py            # SQLAlchemy models (User, Project, Issue, Comment)
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── auth.py              # JWT helpers, password hashing
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Engine, session, Base
│   │   ├── routers/
│   │   │   ├── auth.py          # /auth/register, /auth/login, /auth/me
│   │   │   ├── projects.py      # /projects CRUD
│   │   │   ├── issues.py        # /projects/{id}/issues CRUD + search  ← bugs 1, 3, 4
│   │   │   └── comments.py      # /projects/{id}/issues/{id}/comments CRUD
│   │   └── services/
│   │       └── notifications.py # Stub email service                    ← bug 5
│   └── tests/
│       ├── conftest.py          # SQLite test DB, fixtures
│       ├── test_auth.py
│       └── test_issues.py       # Tests that expose bugs 1 and 2
├── frontend/
│   └── src/
│       ├── app/                 # Next.js App Router pages
│       ├── components/          # Shared UI components
│       └── lib/api.ts           # Axios API client
└── docker-compose.yml
```
