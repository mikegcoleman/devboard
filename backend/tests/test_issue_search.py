"""
Tests for GET /projects/{project_id}/issues/search?q=

Covers all 16 required cases:
1.  Happy path — title match
2.  Case-insensitive title match
3.  Case-insensitive description match
4.  No matches → empty list (200)
5.  Results ordered by updated_at desc
6.  LIKE wildcard escape (%, _)
7.  Issue with NULL description doesn't crash
8.  Project scoping — issues from other projects not returned
9.  401 — unauthenticated
10. 403 — authenticated but not project owner
11. 404 — project does not exist
12. 422 — q param missing or empty
13. Backslash in q is treated as a literal character
"""

import time


# ── Helpers ───────────────────────────────────────────────────────────────────


def _create_issue(
    client,
    auth_headers,
    project_id,
    title="Test issue",
    description="Steps to reproduce...",
    priority="medium",
):
    resp = client.post(
        f"/projects/{project_id}/issues/",
        json={"title": title, "description": description, "priority": priority},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _register_and_login(client, email, username, password="secret123"):
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    resp = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Test cases ────────────────────────────────────────────────────────────────


def test_search_happy_path_title_match(client, auth_headers, project):
    """Case 1: happy path — q matches title of one issue, not the other."""
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


def test_search_case_insensitive_title(client, auth_headers, project):
    """Case 2: uppercase/mixed-case query still matches."""
    _create_issue(client, auth_headers, project["id"], title="Login page crashes on Safari")

    for query in ["LOGIN", "Login", "lOgIn"]:
        resp = client.get(
            f"/projects/{project['id']}/issues/search",
            params={"q": query},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Failed for q={query!r}"
        results = resp.json()
        assert len(results) == 1, f"Expected 1 result for q={query!r}, got {len(results)}"
        assert results[0]["title"] == "Login page crashes on Safari"


def test_search_description_match(client, auth_headers, project):
    """Case 3: q matches description when title does not."""
    _create_issue(
        client,
        auth_headers,
        project["id"],
        title="Misc issue",
        description="fixes login redirect",
    )
    _create_issue(
        client,
        auth_headers,
        project["id"],
        title="Unrelated issue",
        description="nothing to do with the query",
    )

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "login redirect"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Misc issue"


def test_search_no_matches_returns_empty_list(client, auth_headers, project):
    """Case 4: no matches → 200 with empty list, not 404."""
    _create_issue(client, auth_headers, project["id"], title="Some other issue")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "zzznothing"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_ordered_by_updated_at_desc(client, auth_headers, project):
    """Case 5: results ordered by updated_at descending."""
    i1 = _create_issue(client, auth_headers, project["id"], title="login alpha")
    time.sleep(0.1)
    i2 = _create_issue(client, auth_headers, project["id"], title="login beta")
    time.sleep(0.1)
    i3 = _create_issue(client, auth_headers, project["id"], title="login gamma")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "login"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 3
    # Most recently created (and thus updated) should be first
    ids = [r["id"] for r in results]
    assert ids == [i3["id"], i2["id"], i1["id"]]


def test_search_like_wildcard_escape_percent(client, auth_headers, project):
    """Case 6a: literal % in q does not act as LIKE wildcard."""
    _create_issue(client, auth_headers, project["id"], title="Discount 50% off")
    _create_issue(client, auth_headers, project["id"], title="Unrelated item here")

    # q="50%" should match only the discount issue, not everything
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "50%"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Discount 50% off"


def test_search_like_wildcard_escape_percent_alone(client, auth_headers, project):
    """Case 6b: bare % does not match everything — only issues containing literal %."""
    _create_issue(client, auth_headers, project["id"], title="50% complete")
    _create_issue(client, auth_headers, project["id"], title="No wildcard here")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "%"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    # Only the issue with literal % should match
    assert len(results) == 1
    assert "%" in results[0]["title"]


def test_search_like_wildcard_escape_underscore(client, auth_headers, project):
    """Case 6c: literal _ in q does not act as LIKE single-char wildcard."""
    _create_issue(client, auth_headers, project["id"], title="foo_bar issue")
    _create_issue(client, auth_headers, project["id"], title="fooXbar issue")

    # q="foo_bar" with escaping should only match the one with literal underscore
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "foo_bar"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "foo_bar issue"


def test_search_null_description_does_not_crash(client, auth_headers, project):
    """Case 7: issue with NULL description doesn't cause a 500."""
    # Create an issue with no description (NULL)
    resp = client.post(
        f"/projects/{project['id']}/issues/",
        json={"title": "Issue with no description", "priority": "low"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    _create_issue(
        client,
        auth_headers,
        project["id"],
        title="Another issue",
        description="has some text",
    )

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "some text"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Another issue"


def test_search_project_scoping(client, auth_headers, project):
    """Case 8: issues from other projects are not returned."""
    # Create an issue in the fixture project
    _create_issue(client, auth_headers, project["id"], title="login bug in P1")

    # Create a second project and an issue in it
    resp2 = client.post(
        "/projects/",
        json={"name": "Project 2", "description": "second project"},
        headers=auth_headers,
    )
    assert resp2.status_code == 201
    project2 = resp2.json()
    _create_issue(client, auth_headers, project2["id"], title="login crash in P2")

    # Search in P1 — should only return P1's issue
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "login"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "login bug in P1"
    assert results[0]["project_id"] == project["id"]


def test_search_unauthenticated_returns_401(client, project):
    """Case 9: no Authorization header → 401."""
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "anything"},
    )
    assert resp.status_code == 401


def test_search_non_owner_returns_403(client, auth_headers, project):
    """Case 10: authenticated user who is not the project owner gets 403."""
    other_headers = _register_and_login(client, "bob@example.com", "bob")

    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "anything"},
        headers=other_headers,
    )
    assert resp.status_code == 403


def test_search_nonexistent_project_returns_404(client, auth_headers):
    """Case 11: project does not exist → 404."""
    resp = client.get(
        "/projects/999999/issues/search",
        params={"q": "x"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_search_missing_q_returns_422(client, auth_headers, project):
    """Case 12a: missing q param → 422 (FastAPI validation)."""
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_search_empty_q_returns_422(client, auth_headers, project):
    """Case 12b: empty q string (min_length=1) → 422."""
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_search_backslash_in_q_is_literal(client, auth_headers, project):
    """Case 13: backslash in q is escaped correctly and does not cause an error."""
    _create_issue(client, auth_headers, project["id"], title=r"path\to\file issue")
    _create_issue(client, auth_headers, project["id"], title="Unrelated issue")

    # Searching for the literal backslash sequence should match only the right issue
    resp = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": r"path\to"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert "path" in results[0]["title"] and "to" in results[0]["title"]

    # A bare backslash query should not crash — returns empty or matching issues
    resp2 = client.get(
        f"/projects/{project['id']}/issues/search",
        params={"q": "\\"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
