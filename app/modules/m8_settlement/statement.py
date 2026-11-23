from app.catalog import source_data
from app.errors import BusinessError
from app.manifest import digest
from app.modules.m8_settlement.service import settle
from app.pipeline import calculate
from app.quality import token

MONEY_FIELDS = (
    "payable_amount",
    "provisional_amount",
    "withheld_amount",
    "quality_deduction",
)


def build_document(ledger, source):
    """从来源重算管线并生成结算单草稿（含计价裁决）。"""
    if not source:
        raise BusinessError("CHOOSE_SOURCE", "请选择数据来源")
    data = source_data(ledger, source)
    result = calculate(data)
    document = settle(result, data)
    if document["contract"] is None:
        raise BusinessError("CONTRACT_MISSING", "来源缺少结算合同，无法计价")
    return data, result, document


def envelope(ledger, source):
    data, result, document = build_document(ledger, source)
    return {
        "batch": document["batch"],
        "version": 1,
        "sources": [source],
        "current": document,
        "revisions": [
            {
                "source": source,
                "input_sha256": digest(data),
                "digest": document["digest"],
                "status": document["status"],
            }
        ],
        "history": [],
        "confirmed": None,
    }


def merge_revision(existing, draft):
    """同批重试：证据未变沿用旧版；证据变化才追加新版本，旧版进入历史。

    draft 为已由 envelope 算好的草稿，函数只做版本归并，不重算管线。
    """
    document = draft["current"]
    source = draft["sources"][0]
    input_sha = draft["revisions"][0]["input_sha256"]
    if any(rev["input_sha256"] == input_sha for rev in existing["revisions"]):
        return existing, "reused"
    if document["digest"] == existing["current"]["digest"]:
        return existing, "reused"
    history = existing["history"] + [
        {
            "version": existing["version"],
            "source": existing["revisions"][-1]["source"],
            "input_sha256": existing["revisions"][-1]["input_sha256"],
            "digest": existing["current"]["digest"],
            "status": existing["current"]["status"],
            "diff": diff_documents(existing["current"], document),
        }
    ]
    record = {
        "batch": document["batch"],
        "version": existing["version"] + 1,
        "sources": existing["sources"] + [source],
        "current": document,
        "revisions": existing["revisions"]
        + [
            {
                "source": source,
                "input_sha256": input_sha,
                "digest": document["digest"],
                "status": document["status"],
            }
        ],
        "history": history,
        "confirmed": None,
    }
    return record, "revised"


def diff_documents(old, new):
    """逐批料对比新旧结果，工作台据此看清新旧金额与裁决变化。"""
    prior = {line["lot"]: line for line in old["lines"]}
    changes = []
    for line in new["lines"]:
        before = prior.get(line["lot"])
        if before is None:
            changes.append({"lot": line["lot"], "kind": "ADDED", "fields": []})
            continue
        fields = []
        for field in ("status", "grade", "basis", *MONEY_FIELDS):
            if before.get(field) != line.get(field):
                fields.append(
                    {
                        "field": field,
                        "before": before.get(field),
                        "after": line.get(field),
                    }
                )
        if fields:
            changes.append(
                {"lot": line["lot"], "kind": "CHANGED", "fields": fields}
            )
    seen = {line["lot"] for line in new["lines"]}
    for lot, before in prior.items():
        if lot not in seen:
            changes.append({"lot": lot, "kind": "REMOVED", "fields": []})
    return changes


def confirmation(document, operator):
    """正式确认：三证齐全且无磅单冲突才可放款；否则保留旧版，缺证冲突不进应付。"""
    try:
        operator = token(operator)
        if len(operator) > 32:
            raise ValueError
    except ValueError as error:
        raise BusinessError("OPERATOR_REQUIRED", "请输入 1 至 32 字的确认人") from error
    if document["status"] == "BLOCKED" or document["blockers"]:
        raise BusinessError("CONFIRM_BLOCKED", "存在磅单冲突或隔离来源，应付被阻断", 409)
    if document["status"] != "READY" or document["totals"]["ready_lots"] == 0:
        raise BusinessError("CONFIRM_INCOMPLETE", "证据未齐，仅可暂估不可确认放款", 409)
    totals = document["totals"]
    check = {
        "operator": operator,
        "status": "CONFIRMED",
        "payable_amount": totals["payable_amount"],
        "currency": totals["currency"],
        "digest": document["digest"],
    }
    check["signoff"] = digest(check)
    return check
