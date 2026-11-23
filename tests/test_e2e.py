def test_all_workbench_entrypoints(client):
    assert client.get("/api/health").json()["project"] == "gb-0748"
    assert "碎玻璃配载单" in client.get("/").text
    for module in [
        "weighing",
        "moisture",
        "grading",
        "drymass",
        "loading",
        "reconcile",
    ]:
        for source in ("clean", "dirty"):
            response = client.get(f"/api/{module}/{source}")
            assert response.status_code == 200 and response.json()


def test_bad_input_has_no_source_record(client):
    assert client.post("/api/sources", content="坏文件").json()["code"] == "BAD_JSON"
    assert client.post("/api/sources", json={}).status_code == 422
    assert client.get("/api/weighing/absent").json()["code"] == "SOURCE_NOT_FOUND"


def test_oversize_source_is_rejected(client):
    response = client.post("/api/sources", content=b" " * (512 * 1024 + 1))
    assert response.status_code == 413 and response.json()["code"] == "SOURCE_TOO_LARGE"
