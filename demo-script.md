# Docker Agentic Platform Demo — DevBoard (FastAPI/Python)

You are going to demo the Docker Agentic Platform — a system where multiple
specialized AI agents collaborate autonomously to build, review, and ship
modern software. Think of it as an AI development team that works in parallel.

Here's the scenario: we have a FastAPI/Python REST API that has a stubbed-out
search endpoint that needs to be implemented. Walk through the following steps,
using the Agentic Platform tools at each stage. This should feel like watching
a real dev team in action.

---

## STEP 1 — Kick off with the Orchestrator

Send a prompt to the Orchestrator agent:

  "We need to implement the GET /projects/{id}/issues/search?q= endpoint in
   our FastAPI backend. Right now it returns 501 Not Implemented. It should
   do a case-insensitive search across issue title and description, return
   matching issues as a list, and be restricted to the project owner.
   Design it, implement it, write tests, and open a PR."

The orchestrator's job is to *understand the request and fan it out* to the
right specialist agents — it doesn't do the work itself.

---

## STEP 2 — Architect designs the solution (parallel)

The orchestrator delegates to the Architect agent, which produces:
  - A design doc (saved as an artifact) covering:
    - HTTP contract: `GET /projects/{project_id}/issues/search?q=<string>`
    - Pydantic response schema (returns `List[IssueOut]`)
    - SQLAlchemy query strategy: `ilike` on `title` and `description` with `or_()`
    - Authorization: reuse existing `_get_project_or_404` ownership check
    - Error handling: 400 if `q` is empty, 403 if not project owner, 404 if project missing

Show the artifact being created and saved to the project.

---

## STEP 3 — Implementer writes the code (parallel)

While or after the Architect finishes, the orchestrator delegates to the
Implementer agent, passing the design artifact ID. The Implementer:
  - Installs dependencies: `pip install -r backend/requirements.txt`
  - Replaces the `raise HTTPException(status_code=501, ...)` stub in
    `backend/app/routers/issues.py` with the real SQLAlchemy query
  - Writes a pytest test suite in `backend/tests/test_search.py` covering:
      ✅ Matching title → returns results
      ✅ Matching description → returns results
      ✅ Case-insensitive match → returns results
      ✅ No match → returns empty list
      ✅ Empty `q` → 400
      ✅ Non-owner access → 403
  - Runs `pytest backend/tests/test_search.py -v` to confirm all pass
  - Saves all code as artifacts

Show the session-to-session communication (S2S) — the orchestrator spawning
child sessions, work happening in parallel sandboxes.

---

## STEP 4 — Reviewer does a code review

The orchestrator delegates the produced artifacts to the Reviewer agent, which:
  - Checks for SQL injection risk (parameterised queries via SQLAlchemy ORM —
    should be safe, but verify no raw string interpolation into queries)
  - Checks that authorization reuses `_get_project_or_404` and isn't reimplemented
  - Checks Pydantic response model is correct (`List[IssueOut]`, not a raw dict)
  - Checks test coverage completeness (all 6 cases above covered?)
  - Flags any type annotation issues (`mypy`-style) or `ruff` style violations
  - Produces a structured review report as an artifact

Show the review report artifact being pinned to the project for visibility.

---

## STEP 5 — Raise a PR

Once the review passes, the orchestrator instructs the Implementer (with
GitHub identity enabled) to:
  - Commit the changes to a feature branch (`feature/implement-search`)
  - Open a Pull Request with:
      - Title: `Implement issue search endpoint`
      - Description: what was built, the query strategy used, test coverage summary
      - A link to the review report artifact

Show the PR link being saved as a link artifact.

---

## STEP 6 — GitHub Tracker closes the loop

Show the GitHub Tracker agent — it's subscribed to PR events on a channel.
When the PR is opened, it receives the event and notifies the orchestrator,
which updates the kanban board (moving the task card from "In Progress" to
"In Review").

---

## KEY PLATFORM FEATURES TO HIGHLIGHT AT EACH STEP

🔀 **Parallel execution** — Architect and Implementer work simultaneously in
   isolated sandboxes (different sessions), not sequentially.

📡 **Session-to-session (S2S)** — Agents communicate asynchronously. The
   orchestrator never blocks; child sessions report back when done.

📦 **Artifacts** — Every meaningful output (design docs, code, test suites,
   review reports, PR links) is saved as a versioned artifact pinned to the
   project — not lost in a chat window.

🔐 **GitHub identity** — The Implementer agent acts as the user on GitHub
   (opens PRs, pushes branches) via the platform's identity proxy.

📋 **Kanban integration** — Task lifecycle is tracked on the project board
   automatically as agents complete work.

📅 **Event-driven workflows** — The GitHub Tracker uses channels +
   subscriptions to react to real GitHub events without polling.

🧩 **Specialist agents** — Each agent has a focused role and only the tools
   it needs (principle of least privilege).

---

## Codebase context for agents

Repo: https://github.com/mikegcoleman/devboard

Key files:
- `backend/app/routers/issues.py` — the `search_issues` function at line 81
  contains the stub with a commented-out skeleton of the correct implementation
- `backend/app/models.py` — `Issue` model with `title`, `description`, `status`,
  `priority`, `project_id` columns
- `backend/app/schemas.py` — `IssueOut` Pydantic schema (use as response model)
- `backend/tests/conftest.py` — SQLite test DB setup and fixtures to reuse
- `backend/tests/test_issues.py` — existing tests to use as style reference
