"""Logo de l'entreprise sur les bulletins et les lettres.

Dépôt du fichier : `backend/app/assets/logo.png` (ou .jpg), ou n'importe où via la variable d'environnement LOGO_PATH.
Sans fichier, les documents restent exactement comme avant : le logo est facultatif."""
import os
from pathlib import Path
from typing import Optional

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image

DOSSIER = Path(__file__).resolve().parent.parent / "assets"


def chemin_logo() -> Optional[Path]:
    voulu = os.environ.get("LOGO_PATH")
    candidats = [Path(voulu)] if voulu else []
    candidats += [DOSSIER / "logo.png", DOSSIER / "logo.jpg", DOSSIER / "logo.jpeg"]
    return next((c for c in candidats if c.is_file()), None)


def logo(hauteur_mm: float = 16, largeur_max_mm: float = 45) -> Optional[Image]:
    """Image reportlab à la bonne proportion, ou None s'il n'y a pas de logo (ou s'il est illisible)."""
    chemin = chemin_logo()
    if chemin is None:
        return None
    try:
        largeur, hauteur = ImageReader(str(chemin)).getSize()
    except Exception:
        return None
    h = hauteur_mm * mm
    l = h * largeur / hauteur
    if l > largeur_max_mm * mm:
        l, h = largeur_max_mm * mm, largeur_max_mm * mm * hauteur / largeur
    image = Image(str(chemin), width=l, height=h)
    image.hAlign = "LEFT"
    return image
