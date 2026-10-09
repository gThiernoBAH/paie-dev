"""Grille salariale : base horaire par catégorie (datée) × tranches horaires (heures × coefficient).

Salaire mensuel d'une catégorie pour la tranche k = base horaire × heures(k) × coefficient(k), arrondi au franc
(même règle que le legacy). La grille sert de référence : un écart avec le salaire catégoriel d'un salarié est signalé."""
import csv
import io
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models
from . import salaries as svc_salaries

D = Decimal


def _arrondi(v: Decimal) -> Decimal:
    return v.quantize(D(1), rounding=ROUND_HALF_UP)


def tranches(db: Session) -> list:
    return [{"numero": t.numero, "libelle": t.libelle, "heures": t.heures, "coefficient": t.coefficient}
            for t in db.query(models.GrilleTranche).order_by(models.GrilleTranche.numero).all()]


def salaire_tranche(base: Decimal, tranche: models.GrilleTranche) -> Decimal:
    return _arrondi(D(base) * D(tranche.heures) * D(tranche.coefficient))


def base_en_vigueur(db: Session, categorie_id: Optional[int], jour: Optional[date] = None) -> Optional[models.GrilleCategorie]:
    if categorie_id is None:
        return None
    jour = jour or date.today()
    return db.query(models.GrilleCategorie).filter(models.GrilleCategorie.categorie_id == categorie_id, models.GrilleCategorie.date_effet <= jour)\
        .order_by(models.GrilleCategorie.date_effet.desc()).first()


def salaire_grille(db: Session, categorie_id: Optional[int], numero: Optional[int], jour: Optional[date] = None) -> Optional[Decimal]:
    if numero is None:
        return None
    b = base_en_vigueur(db, categorie_id, jour)
    t = db.get(models.GrilleTranche, numero)
    if b is None or t is None:
        return None
    return salaire_tranche(b.base_horaire, t)


def situation(db: Session, s: models.Salarie, jour: Optional[date] = None, montant=None) -> dict:
    """Position du salarié par rapport à la grille : sans_grille, conforme, sous_grille, au_dessus."""
    jour = jour or date.today()
    grille = salaire_grille(db, s.categorie_id, s.tranche, jour)
    if montant is None:
        e = svc_salaries.salaire_en_vigueur(s, jour)
        montant = None if e is None else e.montant
    b = base_en_vigueur(db, s.categorie_id, jour)
    out = {"tranche": s.tranche, "base_horaire": None if b is None else b.base_horaire, "salaire_grille": grille,
           "salaire_actuel": None if montant is None else D(str(montant)), "ecart": None, "statut": "sans_grille"}
    if grille is None or montant is None:
        return out
    out["ecart"] = D(str(montant)) - grille
    out["statut"] = "conforme" if out["ecart"] == 0 else "sous_grille" if out["ecart"] < 0 else "au_dessus"
    return out


def vue_categories(db: Session, jour: Optional[date] = None) -> list:
    jour = jour or date.today()
    ts = db.query(models.GrilleTranche).order_by(models.GrilleTranche.numero).all()
    sortie = []
    for c in db.query(models.Referentiel).filter_by(type_ref="categorie", est_actif=True).order_by(models.Referentiel.ordre, models.Referentiel.code).all():
        b = base_en_vigueur(db, c.id, jour)
        nb = db.query(models.Salarie).filter(models.Salarie.categorie_id == c.id, models.Salarie.est_actif.is_(True)).count()
        sortie.append({"categorie_id": c.id, "code": c.code, "libelle": c.libelle, "nb_salaries": nb,
                       "base_horaire": None if b is None else b.base_horaire, "date_effet": None if b is None else b.date_effet,
                       "salaires": [None if b is None else salaire_tranche(b.base_horaire, t) for t in ts]})
    return sortie


def enregistrer_base(db: Session, categorie_id: int, date_effet: date, base: Decimal, acteur: models.Utilisateur) -> models.GrilleCategorie:
    ref = db.get(models.Referentiel, categorie_id)
    if ref is None or ref.type_ref != "categorie":
        raise ValueError("Catégorie inconnue.")
    g = db.query(models.GrilleCategorie).filter_by(categorie_id=categorie_id, date_effet=date_effet).first()
    if g is None:
        g = models.GrilleCategorie(categorie_id=categorie_id, date_effet=date_effet, base_horaire=base, cree_par=acteur.identifiant)
        db.add(g)
    else:
        g.base_horaire = base
    db.flush()
    return g


def modifier_tranches(db: Session, lignes: list, acteur: models.Utilisateur) -> None:
    for l in lignes:
        t = db.get(models.GrilleTranche, l["numero"])
        if t is None:
            raise ValueError(f"Tranche {l['numero']} inconnue.")
        t.libelle, t.heures, t.coefficient = l["libelle"], l["heures"], l["coefficient"]
        t.modifie_par, t.modifie_le = acteur.identifiant, datetime.now(timezone.utc)
    db.flush()


# ----------------------------------------------------------------- import (copier-coller / CSV du legacy)
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", t).strip()


def _nombre(t: str) -> Optional[Decimal]:
    t = re.sub(r"[\s  ]", "", t or "").replace(",", ".")
    if not t:
        return None
    try:
        v = D(t)
    except InvalidOperation:
        return None
    return v if v > 0 else None


def importer(db: Session, contenu: str, date_effet: date, appliquer: bool, acteur: models.Utilisateur) -> dict:
    """Lit un tableau (CSV, ou copier-coller depuis Excel) avec une colonne CATEGORIE et une colonne BASE HEURE
    (ou, à défaut, « SALAIRE MENSUEL TRANCHE 1 », dont la base est déduite)."""
    texte = contenu.strip("﻿\n\r ")
    if not texte:
        raise ValueError("Aucune donnée à importer.")
    premiere = texte.splitlines()[0]
    sep = max(("\t", ";", ","), key=premiere.count)
    lignes = list(csv.reader(io.StringIO(texte), delimiter=sep))
    entetes = [_norm(h) for h in lignes[0]]

    def col(*mots, sans=()):
        for i, h in enumerate(entetes):
            if all(m in h for m in mots) and not any(x in h for x in sans):
                return i
        return None
    i_cat, i_lib = col("CATEG", sans=("LIBELLE",)), col("LIBELLE")
    i_base = col("BASE")
    i_t1 = col("TRANCHE 1") if col("TRANCHE 1") is not None else col("TRANCHE", "1")
    if i_cat is None:
        raise ValueError("Colonne CATEGORIE introuvable dans la première ligne.")
    if i_base is None and i_t1 is None:
        raise ValueError("Colonne BASE HEURE (ou SALAIRE MENSUEL TRANCHE 1) introuvable dans la première ligne.")
    t1 = db.get(models.GrilleTranche, 1)
    refs = db.query(models.Referentiel).filter_by(type_ref="categorie").all()
    cle = lambda t: _norm(t).replace(" ", "")
    par_code = {cle(r.code): r for r in refs}
    par_lib = {cle(r.libelle): r for r in refs}
    res, appliquees = [], 0
    for brut in lignes[1:]:
        if not any(c.strip() for c in brut):
            continue
        cell = lambda i: brut[i].strip() if i is not None and i < len(brut) else ""
        code, lib = cell(i_cat), cell(i_lib)
        base = _nombre(cell(i_base)) if i_base is not None else None
        if base is None and i_t1 is not None:
            m = _nombre(cell(i_t1))
            if m is not None and t1 is not None and D(t1.heures) * D(t1.coefficient) > 0:
                base = (m / (D(t1.heures) * D(t1.coefficient))).quantize(D("0.0001"))
        ref = par_code.get(cle(code)) or par_lib.get(cle(lib)) or par_lib.get(cle(code))
        etat = "ok" if (ref is not None and base is not None) else ("categorie_inconnue" if ref is None else "base_invalide")
        res.append({"categorie": code, "libelle": lib, "categorie_id": ref.id if ref else None, "base_horaire": base, "etat": etat})
        if appliquer and etat == "ok":
            enregistrer_base(db, ref.id, date_effet, base, acteur)
            appliquees += 1
    return {"lignes": res, "ok": sum(1 for l in res if l["etat"] == "ok"), "ignorees": sum(1 for l in res if l["etat"] != "ok"), "appliquees": appliquees}


# ----------------------------------------------------------------- rapport
def rapport_hors_grille(db: Session, jour: Optional[date] = None) -> dict:
    jour = jour or date.today()
    entetes = ["Matricule", "Nom et prénoms", "Catégorie", "Tranche", "Salaire catégoriel", "Salaire de la grille", "Écart", "Situation"]
    libelles = {"conforme": "Conforme", "sous_grille": "Sous la grille", "au_dessus": "Au-dessus de la grille", "sans_grille": "Sans grille (catégorie, tranche ou base manquante)"}
    lignes = []
    for s in db.query(models.Salarie).filter(models.Salarie.est_actif.is_(True)).order_by(models.Salarie.matricule).all():
        sit = situation(db, s, jour)
        lignes.append([s.matricule, f"{s.nom} {s.prenoms or ''}".strip(), s.categorie.libelle if s.categorie else "", s.tranche or "",
                       sit["salaire_actuel"] if sit["salaire_actuel"] is not None else "", sit["salaire_grille"] if sit["salaire_grille"] is not None else "",
                       sit["ecart"] if sit["ecart"] is not None else "", libelles[sit["statut"]]])
    return {"titre": f"Salariés et grille salariale au {jour.strftime('%d/%m/%Y')}", "entetes": entetes, "lignes": lignes, "totaux": {}}
