from tests.conftest import user_headers


def event(event_type, second, **extra):
    """Mirrors createTelemetryEvent in the mobile app's src/types/telemetry.ts."""
    return {
        "schemaVersion": 1,
        "eventId": f"mock-session-1-{event_type}-{second}",
        "sessionId": "mock-session-1",
        "eventType": event_type,
        "timestamp": f"2026-10-05T10:00:{second:02d}.000Z",
        "deviceTimestamp": None,
        "targetId": None,
        "targetIndex": None,
        "coordinates": None,
        "state": "busy",
        "metrics": None,
        **extra,
    }


def target(event_type, second, index, reaction_ms=None):
    return event(
        event_type,
        second,
        targetId=f"target-{index}",
        targetIndex=index,
        coordinates={"x": index, "y": 1.5},
        metrics={"reactionTimeMs": reaction_ms} if reaction_ms is not None else None,
    )


DRILL = [
    event("SESSION_STARTED", 0),
    target("TARGET_SHOWN", 1, 0),
    target("TARGET_REACHED", 2, 0, 800),
    target("TARGET_SHOWN", 3, 1),
    target("TARGET_REACHED", 4, 1, 1200),
    target("TARGET_SHOWN", 5, 2),
    target("TARGET_MISSED", 6, 2, 1100),
    event("SESSION_COMPLETED", 30),
]


def start_session(client, headers, **body):
    response = client.post(
        "/api/v1/sessions", json={"startedAt": "2026-10-05T10:00:00Z", **body}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_session_lifecycle_and_metrics(client, headers):
    session = start_session(client, headers, name="Custom drill")
    assert session["state"] == "running"
    assert session["completedAt"] is None
    url = f"/api/v1/sessions/{session['id']}"

    partial = client.post(f"{url}/events", json=DRILL[:3], headers=headers)
    assert partial.json() == {"accepted": 3, "duplicates": 0, "state": "running"}

    rest = client.post(f"{url}/events", json=DRILL, headers=headers)
    assert rest.json() == {"accepted": 5, "duplicates": 3, "state": "completed"}

    finished = client.get(url, headers=headers).json()
    assert finished["state"] == "completed"
    assert finished["completedAt"] == "2026-10-05T10:00:30Z"

    metrics = client.get(f"{url}/metrics", headers=headers).json()
    assert metrics == {
        "sessionId": session["id"],
        "exerciseId": None,
        "startedAt": "2026-10-05T10:00:00Z",
        "completedAt": "2026-10-05T10:00:30Z",
        "targetsAttempted": 3,
        "targetsCompleted": 2,
        "targetsMissed": 1,
        "averageTargetTimeMs": 1000.0,
        "fastestTargetTimeMs": 800.0,
        "slowestTargetTimeMs": 1200.0,
        "estimatedCaloriesBurned": None,
    }

    events = client.get(f"{url}/events", headers=headers).json()
    assert [e["eventType"] for e in events] == [e["eventType"] for e in DRILL]
    assert events[2]["coordinates"] == {"x": 0.0, "y": 1.5}
    assert events[2]["metrics"] == {"reactionTimeMs": 800.0}


def test_metrics_for_a_session_without_events(client, headers):
    session = start_session(client, headers)
    metrics = client.get(f"/api/v1/sessions/{session['id']}/metrics", headers=headers).json()
    assert metrics["targetsAttempted"] == 0
    assert metrics["averageTargetTimeMs"] is None


def test_events_are_validated(client, headers):
    session = start_session(client, headers)
    url = f"/api/v1/sessions/{session['id']}/events"
    assert client.post(url, json=[], headers=headers).status_code == 422
    bad_type = client.post(url, json=[event("NOT_A_THING", 1)], headers=headers)
    assert bad_type.status_code == 422
    bad_version = client.post(
        url, json=[event("SESSION_STARTED", 1, schemaVersion=2)], headers=headers
    )
    assert bad_version.status_code == 422


def test_stopped_session(client, headers):
    session = start_session(client, headers)
    response = client.post(
        f"/api/v1/sessions/{session['id']}/events",
        json=[event("SESSION_STARTED", 0), event("SESSION_STOPPED", 5)],
        headers=headers,
    )
    assert response.json()["state"] == "stopped"


def test_session_links_must_belong_to_the_user(client, headers):
    response = client.post("/api/v1/sessions", json={"exerciseId": "missing"}, headers=headers)
    assert response.status_code == 404


def test_sessions_are_private(client, headers):
    session = start_session(client, headers)
    other = user_headers("grace@example.com")
    url = f"/api/v1/sessions/{session['id']}"
    assert client.get(url, headers=other).status_code == 404
    assert client.post(f"{url}/events", json=DRILL, headers=other).status_code == 404
    assert client.get(f"{url}/metrics", headers=other).status_code == 404
    assert client.get("/api/v1/sessions", headers=other).json() == []


def test_analytics_summary(client, headers):
    empty = client.get("/api/v1/analytics/summary", headers=headers).json()
    assert empty["totalSessions"] == 0
    assert empty["accuracyPercent"] is None

    finished = start_session(client, headers)
    client.post(f"/api/v1/sessions/{finished['id']}/events", json=DRILL, headers=headers)
    start_session(client, headers, startedAt="2026-10-06T09:00:00Z")

    other = user_headers("grace@example.com")
    theirs = start_session(client, other)
    client.post(f"/api/v1/sessions/{theirs['id']}/events", json=DRILL, headers=other)

    summary = client.get("/api/v1/analytics/summary", headers=headers).json()
    assert summary == {
        "totalSessions": 2,
        "completedSessions": 1,
        "totalActiveSeconds": 30.0,
        "targetsAttempted": 3,
        "targetsCompleted": 2,
        "targetsMissed": 1,
        "accuracyPercent": 66.7,
        "averageTargetTimeMs": 1000.0,
        "fastestTargetTimeMs": 800.0,
        "slowestTargetTimeMs": 1200.0,
    }

    windowed = client.get(
        "/api/v1/analytics/summary",
        params={"from": "2026-10-06T00:00:00Z", "to": "2026-10-07T00:00:00Z"},
        headers=headers,
    ).json()
    assert windowed["totalSessions"] == 1
    assert windowed["targetsAttempted"] == 0
