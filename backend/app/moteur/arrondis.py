from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENTIMES = Decimal("0.01")
ZERO = Decimal(0)


def d(valeur) -> Decimal:
    """Convertit proprement (jamais via float) en Decimal."""
    if isinstance(valeur, Decimal):
        return valeur
    return Decimal(str(valeur))


def centimes(v: Decimal) -> Decimal:
    return d(v).quantize(CENTIMES, rounding=ROUND_HALF_UP)


def entier_proche(v: Decimal) -> Decimal:
    """Au franc le plus proche (0,5 vers le haut)."""
    return d(v).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def entier_tronque(v: Decimal) -> Decimal:
    return d(v).quantize(Decimal(1), rounding=ROUND_DOWN)


def appliquer_mode(v: Decimal, mode: str) -> Decimal:
    """mode : 'arrondi' (franc le plus proche) ou 'troncature'."""
    return entier_tronque(v) if mode == "troncature" else entier_proche(v)
