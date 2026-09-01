from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


MAIN_BOARD_PREFIXES = ("000", "001", "002", "003", "600", "601", "603", "605")


def is_main_board(code: str) -> bool:
    code = str(code).zfill(6)
    return code.startswith(MAIN_BOARD_PREFIXES)


def exchange_of(code: str) -> str:
    return "SH" if str(code).zfill(6).startswith("6") else "SZ"


def eastmoney_secid(code: str) -> str:
    code = str(code).zfill(6)
    return f"{'1' if code.startswith('6') else '0'}.{code}"


def price_limit_rate(*, is_st: bool = False) -> Decimal:
    return Decimal("0.05") if is_st else Decimal("0.10")


def limit_up_price(previous_close: float | str | Decimal, *, is_st: bool = False) -> float:
    previous = Decimal(str(previous_close))
    price = previous * (Decimal("1") + price_limit_rate(is_st=is_st))
    return float(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def limit_down_price(previous_close: float | str | Decimal, *, is_st: bool = False) -> float:
    previous = Decimal(str(previous_close))
    price = previous * (Decimal("1") - price_limit_rate(is_st=is_st))
    return float(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

