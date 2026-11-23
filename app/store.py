from contextlib import contextmanager
import json
import sqlite3

from app.errors import BusinessError
from app.manifest import canonical


class Ledger:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settlements (
                    batch TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1
                );
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def source(self, identifier):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM sources WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise BusinessError("SOURCE_NOT_FOUND", "未找到数据来源", 404)
        return json.loads(row[0])

    def put_source(self, identifier, payload):
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO sources VALUES (?, ?)",
                (identifier, canonical(payload)),
            )
            return cursor.rowcount == 0

    def run(self, identifier):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM runs WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise BusinessError("RUN_NOT_FOUND", "未找到归档记录", 404)
        return json.loads(row[0])

    def put_run(self, payload):
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO runs VALUES (?, ?)",
                (payload["id"], canonical(payload)),
            )
            return cursor.rowcount == 0

    def settlement(self, batch):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM settlements WHERE batch = ?", (batch,)
            ).fetchone()
        if row is None:
            raise BusinessError("SETTLEMENT_NOT_FOUND", "未找到批次结算单", 404)
        return json.loads(row[0])

    def save_settlement(self, draft):
        """同一批次只保留一张结算单，整个判定在单事务内完成。

        同证据 -> reused（不新增版本）；新证据 -> revised（旧版进历史）；
        已确认 -> confirmed（原样返回，绝不改写）；首次 -> created。
        """
        from app.modules.m8_settlement.statement import merge_revision

        batch = draft["batch"]
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM settlements WHERE batch = ?", (batch,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO settlements (batch, payload, version) VALUES (?, ?, ?)",
                    (batch, canonical(draft), 1),
                )
                return draft, "created"
            existing = json.loads(row[0])
            if existing.get("confirmed"):
                return existing, "confirmed"
            record, outcome = merge_revision(existing, draft)
            if outcome == "reused":
                return existing, "reused"
            conn.execute(
                "UPDATE settlements SET payload = ?, version = ? WHERE batch = ?",
                (canonical(record), record["version"], batch),
            )
            return record, "revised"

    def confirm_settlement(self, batch, confirmation):
        """确认成功才整体替换；冲突或缺证由调用方拦截，旧版本始终保留。"""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM settlements WHERE batch = ?", (batch,)
            ).fetchone()
            if row is None:
                raise BusinessError("SETTLEMENT_NOT_FOUND", "未找到批次结算单", 404)
            current = json.loads(row[0])
            if current.get("confirmed"):
                return current, "already"
            record = dict(current, confirmed=confirmation)
            conn.execute(
                "UPDATE settlements SET payload = ? WHERE batch = ?",
                (canonical(record), batch),
            )
            return record, "confirmed"
