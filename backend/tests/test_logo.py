"""Logo facultatif sur les bulletins et les lettres."""
from io import BytesIO

import pytest

from app.exports import logo as logo_pdf
from tests.conftest import connexion, creer_compte
from tests.test_campagnes import preparer_gt10
from tests.test_discipline_gratifications import mesure
from tests.test_virements_declarations import salarie  # noqa: F401


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def _png(chemin):
    from PIL import Image
    Image.new("RGB", (200, 80), (30, 90, 160)).save(chemin)


def test_sans_logo_rien_ne_change(monkeypatch):
    monkeypatch.setenv("LOGO_PATH", "/inexistant/logo.png")
    monkeypatch.setattr(logo_pdf, "DOSSIER", logo_pdf.DOSSIER / "vide")
    assert logo_pdf.logo() is None


def test_logo_illisible_ignore(monkeypatch, tmp_path):
    f = tmp_path / "logo.png"
    f.write_bytes(b"pas une image")
    monkeypatch.setenv("LOGO_PATH", str(f))
    assert logo_pdf.logo() is None


def test_pdf_avec_logo(client, db, admin, monkeypatch, tmp_path):
    f = tmp_path / "logo.png"
    _png(f)
    monkeypatch.setenv("LOGO_PATH", str(f))
    assert logo_pdf.logo() is not None
    cid, _ = preparer_gt10(client, db, admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    bid = client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]["id"]
    r = client.get(f"/bulletins/{bid}/pdf", headers=admin)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    from pypdf import PdfReader
    p = PdfReader(BytesIO(r.content)).pages[0]
    assert "205 014" in p.extract_text() and len(p.images) == 1
    sid = salarie(client, admin, "7")
    m = mesure(client, admin, sid)
    pdf = client.get(f"/discipline/mesures/{m.json()['id']}/lettre.pdf", headers=admin)
    assert pdf.status_code == 200 and len(PdfReader(BytesIO(pdf.content)).pages[0].images) == 1
