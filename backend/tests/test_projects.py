def test_project_crud(client):
    res = client.post(
        "/api/v1/projects",
        json={"topic": "Hidden coral reefs", "target_duration_seconds": 30},
    )
    assert res.status_code == 200
    project = res.json()
    assert project["topic"] == "Hidden coral reefs"
    pid = project["id"]

    res = client.get(f"/api/v1/projects/{pid}")
    assert res.status_code == 200

    res = client.get(f"/api/v1/projects/{pid}/manifest")
    assert res.status_code == 200
    manifest = res.json()
    assert manifest["project_id"] == pid
    assert manifest["pipeline_stages"][0]["status"] == "completed"

    res = client.patch(f"/api/v1/projects/{pid}", json={"title": "Reef Secrets"})
    assert res.json()["title"] == "Reef Secrets"

    res = client.post(f"/api/v1/projects/{pid}/duplicate")
    assert res.status_code == 200
    assert "Copy" in res.json()["title"]

    res = client.get("/api/v1/projects")
    assert res.json()["total"] >= 2

    res = client.delete(f"/api/v1/projects/{pid}")
    assert res.status_code == 200


def test_health(client):
    res = client.get("/api/v1/system/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
