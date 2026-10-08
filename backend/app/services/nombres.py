"""Montants en toutes lettres (orthographe française, FCFA)."""

UNITES = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
          "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
DIZAINES = ["", "", "vingt", "trente", "quarante", "cinquante", "soixante"]


def _moins_de_cent(n: int, final: bool) -> str:
    if n < 20:
        return UNITES[n]
    if n < 70:
        d, u = divmod(n, 10)
        if u == 0:
            return DIZAINES[d]
        return DIZAINES[d] + ("-et-un" if u == 1 else "-" + UNITES[u])
    if n < 80:                                    # 70-79 : soixante-dix...
        return "soixante-et-onze" if n == 71 else "soixante-" + UNITES[n - 60]
    if n == 80:
        return "quatre-vingts" if final else "quatre-vingt"
    return "quatre-vingt-" + UNITES[n - 80]       # 81-99


def _moins_de_mille(n: int, final: bool) -> str:
    centaines, reste = divmod(n, 100)
    if centaines == 0:
        return _moins_de_cent(reste, final)
    debut = "cent" if centaines == 1 else UNITES[centaines] + " cent"
    if reste == 0:
        return debut + ("s" if centaines > 1 and final else "")
    return debut + " " + _moins_de_cent(reste, final)


def en_lettres(n: int) -> str:
    """12 345 -> « douze mille trois cent quarante-cinq »."""
    n = int(n)
    if n < 0:
        return "moins " + en_lettres(-n)
    if n == 0:
        return "zéro"
    morceaux = []
    for valeur, nom in ((1_000_000_000, "milliard"), (1_000_000, "million")):
        q, n = divmod(n, valeur)
        if q:
            morceaux.append(f"{_moins_de_mille(q, False)} {nom}" + ("s" if q > 1 else ""))
    q, n = divmod(n, 1000)
    if q:
        morceaux.append("mille" if q == 1 else f"{_moins_de_mille(q, False)} mille")
    if n:
        morceaux.append(_moins_de_mille(n, True))
    return " ".join(morceaux)


def montant_en_lettres(montant) -> str:
    return en_lettres(int(round(float(montant)))).capitalize() + " francs CFA"
