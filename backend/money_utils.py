"""Aritmetica monetaria e delle ore per la rendicontazione (DOM-11).

REGOLA UNICA DI ARROTONDAMENTO: ROUND_HALF_UP a 2 decimali
(arrotondamento commerciale, lo stesso dei fogli di verifica dei fondi).
Mai round() di Python sui valori economici: usa il banker's rounding
(round-half-even) e produce derive da 1 centesimo rispetto ai controlli
del fondo (es. 10,5 × 33,33 = 349,965 → 349,96 invece di 349,97).

I float NON vanno passati direttamente a Decimal: Decimal(2.675) è
2.67499999...; la conversione corretta passa da str.
"""

from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def to_decimal(value) -> Decimal:
    """Converte in Decimal in modo sicuro (float via str, None -> 0)."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(str(value))


def quantize_euro(value) -> Decimal:
    """Importo in euro quantizzato a 2 decimali, ROUND_HALF_UP."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def quantize_ore(value) -> Decimal:
    """Ore (anche frazionarie) quantizzate a 2 decimali, ROUND_HALF_UP."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
