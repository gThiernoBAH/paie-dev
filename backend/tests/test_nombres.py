import pytest

from app.services.nombres import en_lettres, montant_en_lettres


@pytest.mark.parametrize("n,attendu", [
    (0, "zéro"), (1, "un"), (16, "seize"), (21, "vingt-et-un"), (71, "soixante-et-onze"), (80, "quatre-vingts"),
    (81, "quatre-vingt-un"), (99, "quatre-vingt-dix-neuf"), (100, "cent"), (200, "deux cents"), (201, "deux cent un"),
    (1000, "mille"), (2000, "deux mille"), (80000, "quatre-vingt mille"), (205014, "deux cent cinq mille quatorze"),
    (768712, "sept cent soixante-huit mille sept cent douze"), (1_000_000, "un million"),
    (2_500_000, "deux millions cinq cent mille"), (1_000_000_000, "un milliard"),
])
def test_en_lettres(n, attendu):
    assert en_lettres(n) == attendu


def test_montant():
    assert montant_en_lettres(18194) == "Dix-huit mille cent quatre-vingt-quatorze francs CFA"
