from app.errors import BusinessError
from app.modules.m3_grading.classes import GRADES
from app.modules.m8_settlement.money import Decimal, yuan
from app.quality import number, token

KEYS = ("currency", "wet_floor_price", "grade_prices", "provisional_reserve_rate")


def contract(data):
    """解析并校验结算合同；缺段返回 None（该来源不具备计价依据）。"""
    raw = data.get("contract")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BusinessError("BAD_CONTRACT", "结算合同须为对象")
    try:
        currency = token(raw["currency"])
        if len(currency) > 8:
            raise ValueError
        floor = yuan(number(raw["wet_floor_price"]))
        prices_raw = raw["grade_prices"]
        reserve = number(raw["provisional_reserve_rate"])
    except (KeyError, TypeError, ValueError) as error:
        raise BusinessError("BAD_CONTRACT", "结算合同字段或金额无效") from error
    if floor < 0 or not 0 <= reserve <= 1:
        raise BusinessError("BAD_CONTRACT", "暂估暂扣比例须在 0 至 1 之间")
    if not isinstance(prices_raw, dict):
        raise BusinessError("BAD_CONTRACT", "色级单价须为对象")
    prices = {}
    for grade in GRADES:
        try:
            price = yuan(number(prices_raw[grade]))
        except (KeyError, TypeError, ValueError) as error:
            raise BusinessError(
                "BAD_CONTRACT", f"缺少色级 {grade} 的有效单价"
            ) from error
        if price < 0:
            raise BusinessError("BAD_CONTRACT", "色级单价不能为负")
        prices[grade] = price
    unknown = set(prices_raw).difference(GRADES)
    if unknown:
        raise BusinessError("BAD_CONTRACT", f"未知色级单价：{sorted(unknown)}")
    return {
        "currency": currency,
        "wet_floor_price": format(floor, ".2f"),
        "grade_prices": {grade: format(prices[grade], ".2f") for grade in sorted(prices)},
        "provisional_reserve_rate": str(Decimal(reserve)),
    }
