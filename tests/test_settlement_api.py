import copy
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app


def register(client, source):
    return client.post("/api/settlements", json={"source": source})


def test_register_creates_single_statement_per_batch(client):
    record = register(client, "dirty").json()
    assert record["outcome"] == "created" and record["version"] == 1
    again = register(client, "dirty").json()
    assert again["outcome"] == "reused"
    assert again["current"]["digest"] == record["current"]["digest"]
    assert again["version"] == 1


def test_concurrent_register_does_not_duplicate(client):
    with ThreadPoolExecutor(4) as pool:
        records = list(
            pool.map(lambda _: register(client, "dirty").json(), range(4))
        )
    assert len({row["batch"] for row in records}) == 1
    assert {row["version"] for row in records} == {1}
    assert {row["outcome"] for row in records} <= {"created", "reused"}


def test_new_evidence_appends_revision_and_keeps_history(client, dirty):
    first = register(client, "dirty").json()
    grown = copy.deepcopy(dirty)
    grown["grades"].append(
        {"lot": "L08", "color": "白", "offcolor": "2.6", "impurity": "0.55", "unit": "%"}
    )
    source = client.post("/api/sources", json=grown).json()["source"]
    second = register(client, source).json()
    assert second["outcome"] == "revised" and second["version"] == 2
    assert len(second["revisions"]) == 2 and len(second["history"]) == 1
    old = second["history"][0]
    assert old["digest"] == first["current"]["digest"]
    changed = next(item for item in old["diff"] if item["lot"] == "L08")
    assert changed["kind"] == "CHANGED"
    assert "quality_deduction" in {field["field"] for field in changed["fields"]}
    # 批次不变，库里始终只有一张结算单
    assert second["batch"] == first["batch"]


def test_confirm_failure_keeps_old_statement(client):
    record = register(client, "dirty").json()
    response = client.post(
        f"/api/settlements/{record['batch']}/confirm",
        json={"operator": "财务甲"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFIRM_BLOCKED"
    stored = client.get(f"/api/settlements/{record['batch']}").json()
    assert stored["confirmed"] is None
    assert stored["current"]["digest"] == record["current"]["digest"]


def test_provisional_only_batch_cannot_be_confirmed(client, clean):
    # 去掉 L01 分级样：证据未齐，只能暂估
    clean["grades"] = [row for row in clean["grades"] if row["lot"] != "L01"]
    source = client.post("/api/sources", json=clean).json()["source"]
    record = register(client, source).json()
    assert record["current"]["status"] == "PROVISIONAL"
    response = client.post(
        f"/api/settlements/{record['batch']}/confirm",
        json={"operator": "财务甲"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFIRM_INCOMPLETE"


def test_full_evidence_batch_confirms_and_locks(client):
    record = register(client, "clean").json()
    confirmed = client.post(
        f"/api/settlements/{record['batch']}/confirm",
        json={"operator": "财务甲"},
    ).json()
    assert confirmed["outcome"] == "confirmed"
    assert confirmed["confirmed"]["status"] == "CONFIRMED"
    assert confirmed["confirmed"]["payable_amount"] == "5976.74"
    # 确认后同批再登记不产生新单、不改版本
    again = register(client, "clean").json()
    assert again["outcome"] == "confirmed"
    assert again["version"] == record["version"]
    # 重复确认沿用首次签核
    repeat = client.post(
        f"/api/settlements/{record['batch']}/confirm",
        json={"operator": "财务乙"},
    ).json()
    assert repeat["outcome"] == "already"
    assert repeat["confirmed"]["operator"] == "财务甲"


def test_rerun_never_creates_second_statement(client):
    record = register(client, "clean").json()
    rerun = client.post(f"/api/settlements/{record['batch']}/rerun").json()
    assert rerun["current"]["digest"] == record["current"]["digest"]


def test_preview_and_missing_contract(client, clean):
    preview = client.get("/api/settlements/preview/clean").json()
    assert preview["status"] == "READY"
    del clean["contract"]
    source = client.post("/api/sources", json=clean).json()["source"]
    assert client.get(f"/api/settlements/preview/{source}").json()["status"] == (
        "NO_CONTRACT"
    )
    missing = register(client, source)
    assert missing.status_code == 422
    assert missing.json()["code"] == "CONTRACT_MISSING"


def test_settlement_persists_across_sessions(tmp_path, dirty):
    db = tmp_path / "state.sqlite3"
    with TestClient(create_app(db)) as first:
        record = register(first, "dirty").json()
    with TestClient(create_app(db)) as second:
        stored = second.get(f"/api/settlements/{record['batch']}").json()
        assert stored["version"] == 1
        assert stored["current"]["digest"] == record["current"]["digest"]


def test_empty_batch_cannot_be_confirmed(client, clean):
    clean["tickets"] = []
    source = client.post("/api/sources", json=clean).json()["source"]
    record = register(client, source).json()
    assert record["current"]["totals"]["lot_count"] == 0
    response = client.post(
        f"/api/settlements/{record['batch']}/confirm",
        json={"operator": "财务甲"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFIRM_INCOMPLETE"


def test_unknown_batch_and_operator_validation(client):
    register(client, "dirty")
    missing = client.get("/api/settlements/NO-SUCH-BATCH")
    assert missing.status_code == 404
    assert missing.json()["code"] == "SETTLEMENT_NOT_FOUND"
    bad = client.post(
        "/api/settlements/BL-1120-21/confirm", json={"operator": ""}
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "OPERATOR_REQUIRED"
