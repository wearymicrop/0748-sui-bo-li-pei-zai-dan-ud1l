from app.errors import BusinessError
from app.modules.m8_settlement.statement import confirmation, envelope


def register(ledger, source):
    """车队当天暂估：同批同证据不新增结算单，新证据只升版本。

    构造与写入分离；版本归并和并发安全由账本单事务保证。
    """
    draft = envelope(ledger, source)
    return ledger.save_settlement(draft)


def confirm(ledger, batch, operator):
    """财务正式确认：失败时抛错且旧版结算单原样保留。"""
    existing = ledger.settlement(batch)
    if existing.get("confirmed"):
        return existing, "already"
    check = confirmation(existing["current"], operator)
    return ledger.confirm_settlement(batch, check)


def rerun(ledger, batch):
    """同批复算：只核对最新版本摘要，绝不生成第二张结算单。"""
    existing = ledger.settlement(batch)
    source = existing["sources"][-1]
    draft = envelope(ledger, source)
    if draft["current"]["digest"] != existing["current"]["digest"]:
        raise BusinessError(
            "REVISION_CONFLICT", "结算单已被更新，请基于最新版本重试", 409
        )
    return existing
