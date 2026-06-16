"""
Tests for the issues router.

Several tests here are designed to expose known bugs in the implementation.
Run these tests with:  pytest tests/test_issues.py -v
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _create_issue(client, auth_headers, project_id, title="Bug: login fails", priority="high", description="Steps to reproduce..."):
    resp = client.post(
        f"/projects/{project_id}/issues/",
        json={"title": title, "description": description, "priority": priority},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


def _register_and_login(client, email, username, password="secret123"):
    """Register a new user and return their auth headers."""
    resp = client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert resp.status_code == 201
    resp = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Basic CRUD ────────────────────────────────────────────────────────────────


def test_create_issue(client, auth_headers, project):
    issue = _create_issue(client, auth_headers, project["id"])
    assert issue["title"] == "Bug: login fails"
    assert issue["status"] == "open"
    assert issue["priority"] == "high"


def test_get_issue(client, auth_headers, project):
    created = _create_issue(client, auth_headers, project["id"])
    resp = client.get(
        f"/projects/{project['id']}/issues/{created['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_update_issue_status(client, auth_headers, project):
    issue = _create_issue(client, auth_headers, project["id"])
    resp = client.put(
        f"/projects/{project['id']}/issues/{issue['id']}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_delete_issue(client, auth_headers, project):
    issue = _create_issue(client, auth_headers, project["id"])
    resp = client.delete(
        f"/projects/{project['id']}/issues/{issue['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 204


# ── Pagination bug ────────────────────────────────────────────────────────────


def test_pagination_first_page_returns_results(client, auth_headers, project):
    """
    BUG TEST: page=1 should return the first page_size items, not skip them.

    With the bug (skip = page * page_size), requesting page=1 with page_size=3
    skips items 0-2 instead of returning them.  This test will FAIL until
    the bug is fixed (skip should be (page - 1) * page_size).
    """
    titles = ["Issue A", "Issue B", "Issue C", "Issue D", "Issue E"]
    for t in titles:
        _create_issue(client, auth_headers, project["id"], title=t)

    resp = client.get(
        f"/projects/{project['id']}/issues/",
        params={"page": 1, "page_size": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Page 1 should return exactly 3 items. With the bug it returns fewer
    # because it's skipping 3 items from a 5-item list.
    assert len(data["items"]) == 3, (
        f"Expected 3 items on page 1 but got {len(data['items'])}. "
        "Hint: check the skip calculation in list_issues()."
    )


def test_pagination_total_count(client, auth_headers, project):
    """Total count should match regardless of page."""
    for i in range(7):
        _create_issue(client, auth_headers, project["id"], title=f"Issue {i}")

    resp = client.get(
        f"/projects/{project['id']}/issues/",
        params={"page": 1, "page_size": 3},
        headers=auth_headers,
    )
    assert resp.json()["total"] == 7


def test_pagination_second_page(client, auth_headers, project):
    """Items on page 2 should be different from items on page 1."""
    for i in range(6):
        _create_issue(client, auth_headers, project["id"], title=f"Issue {i}")

    page1 = client.get(
        f"/projects/{project['id']}/issues/",
        params={"page": 1, "page_size": 3},
        headers=auth_headers,
    ).json()["items"]

    page2 = client.get(
        f"/projects/{project['id']}/issues/",
        params={"page": 2, "page_size": 3},
        headers=auth_headers,
    ).json()["items"]

    page1_ids = {i["id"] for i in page1}
    page2_ids = {i["id"] for i in page2}
    assert page1_ids.isdisjoint(page2_ids), (
        "Page 1 and page 2 contain overlapping items — pagination is broken."
    )


# ── Search ────────────────────────────────────────────────────────────────────


def test_search_finds_matching_issues(client, auth_headers, project):
    """Search returns issues whose title contains the query string."""
    _create_issue(client, auth_headers, project["id"], title="Login page crashes on Safari")
    _create_issue(client, auth_headers, project["id"], title="Dashboard layout broken")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "login"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Login page crashes on Safari"


def test_search_case_insensitive(client, auth_headers, project):
    """Search is case-insensitive: q=LOGIN finds 'Login page crashes on Safari'."""
    _create_issue(client, auth_headers, project["id"], title="Login page crashes on Safari")
    _create_issue(client, auth_headers, project["id"], title="Dashboard layout broken")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "LOGIN"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Login page crashes on Safari"


def test_search_matches_description(client, auth_headers, project):
    """Search also matches against the description field."""
    _create_issue(
        client, auth_headers, project["id"],
        title="Unrelated",
        description="This is about authentication",
    )
    _create_issue(
        client, auth_headers, project["id"],
        title="Something else",
        description="Totally unrelated content",
    )

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "authentication"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Unrelated"


def test_search_no_match_returns_empty_list(client, auth_headers, project):
    """Search with no matching results returns 200 with an empty list."""
    _create_issue(client, auth_headers, project["id"], title="Login page crashes on Safari")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "xyznotfound"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_requires_auth(client, project):
    """Unauthenticated request to search returns 401."""
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "login"},
    )
    assert resp.status_code == 401


def test_search_nonexistent_project_returns_404(client, auth_headers):
    """Search on a non-existent project returns 404."""
    resp = client.get(
        "/projects/99999/issues/search",
        params={"q": "login"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_search_null_description_does_not_crash(client, auth_headers, project):
    """Issues with null description don't cause errors; title match still works."""
    # Create an issue with no description (None) — title matches the query
    resp = client.post(
        f"/projects/{project['id']}/issues/",
        json={"title": "Login timeout error", "priority": "medium"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    # Create another issue with no description whose title does NOT match
    resp2 = client.post(
        f"/projects/{project['id']}/issues/",
        json={"title": "Unrelated issue", "priority": "low"},
        headers=auth_headers,
    )
    assert resp2.status_code == 201

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "timeout"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Login timeout error"


def test_search_scoped_to_project(client, auth_headers):
    """Search results are scoped to the requested project — no cross-project leakage."""
    # Create project A
    resp_a = client.post(
        "/projects/",
        json={"name": "Project A", "description": "First project"},
        headers=auth_headers,
    )
    assert resp_a.status_code == 201
    project_a = resp_a.json()

    # Create project B
    resp_b = client.post(
        "/projects/",
        json={"name": "Project B", "description": "Second project"},
        headers=auth_headers,
    )
    assert resp_b.status_code == 201
    project_b = resp_b.json()

    # Add a matching issue only to project A
    _create_issue(client, auth_headers, project_a["id"], title="Login bug in project A")

    # Search in project B — should return empty list
    resp = client.get(
        f"/projects/{project_b['id']}/issues/search",
        params={"q": "login"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_non_owner_returns_403(client, auth_headers, project):
    """A second user searching a project they don't own receives 403."""
    second_user_headers = _register_and_login(client, "bob@example.com", "bob")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "login"},
        headers=second_user_headers,
    )
    assert resp.status_code == 403


def test_search_missing_q_returns_422(client, auth_headers, project):
    """Calling the search endpoint with no q param returns 422 (FastAPI validation)."""
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── updated_at bug ────────────────────────────────────────────────────────────


def test_updated_at_changes_on_update(client, auth_headers, project):
    """
    BUG TEST: updated_at should change when an issue is updated.

    With the bug (no onupdate= in the Column definition), the timestamp
    stays frozen at creation time. This test will FAIL until the model
    is fixed to include onupdate=datetime.utcnow.
    """
    import time

    issue = _create_issue(client, auth_headers, project["id"])
    original_updated_at = issue["updated_at"]

    time.sleep(1)  # ensure at least 1s passes

    resp = client.put(
        f"/projects/{project['id']}/issues/{issue['id']}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    new_updated_at = resp.json()["updated_at"]

    assert new_updated_at != original_updated_at, (
        f"updated_at did not change after update: {original_updated_at} == {new_updated_at}. "
        "Hint: add onupdate=datetime.utcnow to the updated_at Column in models.py."
    )
