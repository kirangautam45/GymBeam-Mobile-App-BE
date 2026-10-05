from tests.conftest import user_headers

TARGETS = [{"x": -1, "y": 1.5}, {"x": 0.5, "y": 3}, {"x": 2, "y": 0.5}]


def create_pattern(client, headers, name="Triangle"):
    response = client.post(
        "/api/v1/patterns", json={"name": name, "targets": TARGETS}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_exercise(client, headers, pattern_id, **overrides):
    payload = {
        "name": "Warm up",
        "difficulty": "beginner",
        "estimatedDurationSeconds": 120,
        "patternId": pattern_id,
        "tags": ["agility"],
        **overrides,
    }
    response = client.post("/api/v1/exercises", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_endpoints_require_auth(client):
    for path in ("patterns", "exercises", "devices", "sessions", "analytics/summary"):
        assert client.get(f"/api/v1/{path}").status_code == 401


def test_pattern_crud(client, headers):
    pattern = create_pattern(client, headers)
    assert pattern["targets"] == [{"x": -1.0, "y": 1.5}, {"x": 0.5, "y": 3.0}, {"x": 2.0, "y": 0.5}]
    assert pattern["createdAt"].endswith("Z")

    assert client.get("/api/v1/patterns", headers=headers).json() == [pattern]

    updated = client.put(
        f"/api/v1/patterns/{pattern['id']}",
        json={"name": "Line", "targets": TARGETS[:2]},
        headers=headers,
    ).json()
    assert updated["name"] == "Line"
    assert len(updated["targets"]) == 2

    assert client.delete(f"/api/v1/patterns/{pattern['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/patterns/{pattern['id']}", headers=headers).status_code == 404


def test_pattern_needs_at_least_one_target(client, headers):
    response = client.post(
        "/api/v1/patterns", json={"name": "Empty", "targets": []}, headers=headers
    )
    assert response.status_code == 422


def test_exercise_crud(client, headers):
    pattern = create_pattern(client, headers)
    exercise = create_exercise(client, headers, pattern["id"])
    assert exercise["targetCount"] == 3
    assert exercise["sets"] == 1
    assert exercise["isFavorite"] is False

    patched = client.patch(
        f"/api/v1/exercises/{exercise['id']}", json={"isFavorite": True}, headers=headers
    ).json()
    assert patched["isFavorite"] is True
    assert patched["name"] == "Warm up"

    favorites = client.get("/api/v1/exercises?favorite=true", headers=headers).json()
    assert [e["id"] for e in favorites] == [exercise["id"]]
    assert client.get("/api/v1/exercises?favorite=false", headers=headers).json() == []

    in_use = client.delete(f"/api/v1/patterns/{pattern['id']}", headers=headers)
    assert in_use.status_code == 409

    assert client.delete(f"/api/v1/exercises/{exercise['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/patterns/{pattern['id']}", headers=headers).status_code == 204


def test_exercise_rejects_unknown_pattern(client, headers):
    response = client.post(
        "/api/v1/exercises",
        json={
            "name": "Orphan",
            "difficulty": "advanced",
            "estimatedDurationSeconds": 60,
            "patternId": "missing",
        },
        headers=headers,
    )
    assert response.status_code == 404


def test_users_cannot_see_each_others_data(client, headers):
    pattern = create_pattern(client, headers)
    exercise = create_exercise(client, headers, pattern["id"])
    other = user_headers("grace@example.com")

    assert client.get("/api/v1/patterns", headers=other).json() == []
    assert client.get(f"/api/v1/patterns/{pattern['id']}", headers=other).status_code == 404
    assert client.get(f"/api/v1/exercises/{exercise['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/exercises/{exercise['id']}", headers=other).status_code == 404
    borrowed = client.post(
        "/api/v1/exercises",
        json={
            "name": "Borrowed",
            "difficulty": "beginner",
            "estimatedDurationSeconds": 60,
            "patternId": pattern["id"],
        },
        headers=other,
    )
    assert borrowed.status_code == 404


def test_device_pairing_is_idempotent_per_mac(client, headers):
    payload = {
        "name": "GymBeam Pi",
        "macAddress": "b8:27:eb:00:11:22",
        "deviceType": "raspberry-pi",
    }
    first = client.post("/api/v1/devices", json=payload, headers=headers)
    assert first.status_code == 201
    assert first.json()["macAddress"] == "B8:27:EB:00:11:22"
    assert first.json()["metrics"] is None

    again = client.post("/api/v1/devices", json={**payload, "name": "Studio Pi"}, headers=headers)
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["name"] == "Studio Pi"
    assert len(client.get("/api/v1/devices", headers=headers).json()) == 1

    metrics = {
        "cpuUsagePercent": 18.5,
        "memoryUsagePercent": 42,
        "diskUsagePercent": 22,
        "temperatureCelsius": 47.1,
        "uptimeSeconds": 3600,
        "reportedAt": "2026-10-05T10:00:00Z",
    }
    reported = client.put(
        f"/api/v1/devices/{first.json()['id']}/metrics", json=metrics, headers=headers
    )
    assert reported.status_code == 200
    assert reported.json()["metrics"]["cpuUsagePercent"] == 18.5
    assert reported.json()["metrics"]["reportedAt"] == "2026-10-05T10:00:00Z"

    assert (
        client.delete(f"/api/v1/devices/{first.json()['id']}", headers=headers).status_code == 204
    )
    assert client.get("/api/v1/devices", headers=headers).json() == []
