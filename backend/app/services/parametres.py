"""Lecture et validation des paramètres (taux, plafonds, barèmes...).

Le moteur de paie ne lit JAMAIS une constante en dur : il appelle `lire(db, cle, date)`, qui renvoie
la valeur en vigueur à la date demandée (la plus récente dont la date d'effet est <= date).
"""
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..core.models import Parametre, ValeurParametre

NOMBRES = ("entier", "decimal", "montant", "pourcentage")


class ParametreIntrouvable(LookupError):
    pass


class ValeurInvalide(ValueError):
    """Message en français, affichable tel quel à l'utilisateur."""


def _decimal(brut: Any, libelle: str) -> Decimal:
    try:
        d = Decimal(str(brut).strip().replace(",", ".").replace(" ", "").replace(" ", ""))
    except InvalidOperation:
        raise ValeurInvalide(f"« {brut} » n'est pas un nombre.")
    if not d.is_finite():
        raise ValeurInvalide(f"« {brut} » n'est pas un nombre.")
    return d


def _nombre_json(d: Decimal):
    return int(d) if d == d.to_integral_value() else float(d)


def _normaliser_bareme(brut: Any) -> str:
    try:
        tranches = json.loads(brut, parse_float=Decimal, parse_int=Decimal) if isinstance(brut, str) else brut
    except json.JSONDecodeError:
        raise ValeurInvalide("Le barème n'est pas lisible.")
    if not isinstance(tranches, list) or not tranches:
        raise ValeurInvalide("Le barème doit contenir au moins une tranche.")
    propres, precedente = [], Decimal(0)
    for i, t in enumerate(tranches, start=1):
        if not isinstance(t, dict) or "taux" not in t:
            raise ValeurInvalide(f"Tranche {i} : taux manquant.")
        taux = _decimal(t["taux"], "taux")
        if not (0 <= taux <= 100):
            raise ValeurInvalide(f"Tranche {i} : le taux doit être compris entre 0 et 100.")
        borne = t.get("jusqu_a")
        derniere = i == len(tranches)
        if derniere:
            if borne not in (None, ""):
                raise ValeurInvalide("La dernière tranche ne doit pas avoir de limite (« et au-delà »).")
            propres.append({"jusqu_a": None, "taux": _nombre_json(taux)})
        else:
            if borne in (None, ""):
                raise ValeurInvalide(f"Tranche {i} : la limite est obligatoire (seule la dernière tranche n'en a pas).")
            borne = _decimal(borne, "limite")
            if borne <= precedente:
                raise ValeurInvalide(f"Tranche {i} : les limites doivent être strictement croissantes.")
            precedente = borne
            propres.append({"jusqu_a": _nombre_json(borne), "taux": _nombre_json(taux)})
    return json.dumps(propres)


def normaliser(parametre: Parametre, brut: Any) -> str:
    """Contrôle `brut` selon la définition du paramètre et renvoie sa forme stockée (texte canonique)."""
    t = parametre.type_valeur
    if t in NOMBRES:
        d = _decimal(brut, parametre.libelle)
        if t == "entier" and d != d.to_integral_value():
            raise ValeurInvalide("Un nombre entier est attendu.")
        if t == "pourcentage" and not (0 <= d <= 1000):
            raise ValeurInvalide("Pourcentage invalide.")
        if parametre.valeur_min is not None and d < parametre.valeur_min:
            raise ValeurInvalide(f"La valeur doit être au moins {parametre.valeur_min.normalize():f}.")
        if parametre.valeur_max is not None and d > parametre.valeur_max:
            raise ValeurInvalide(f"La valeur doit être au plus {parametre.valeur_max.normalize():f}.")
        return str(int(d)) if t == "entier" else f"{d.normalize():f}"
    if t == "booleen":
        v = str(brut).strip().lower()
        if v not in ("true", "false"):
            raise ValeurInvalide("Oui ou non attendu.")
        return v
    if t == "heure":
        v = str(brut).strip()
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValeurInvalide("Heure attendue au format HH:MM.")
        return v
    if t == "bareme":
        return _normaliser_bareme(brut)
    v = str(brut).strip()
    if not v:
        raise ValeurInvalide("Une valeur est obligatoire.")
    if len(v) > 300:
        raise ValeurInvalide("Texte trop long (300 caractères maximum).")
    if parametre.choix and v not in [c.strip() for c in parametre.choix.split(",")]:
        raise ValeurInvalide(f"Valeur autorisée : {parametre.choix.replace(',', ', ')}.")
    return v


def convertir(parametre: Parametre, stockee: str) -> Any:
    """Valeur stockée -> valeur typée pour le moteur (Decimal pour les nombres)."""
    t = parametre.type_valeur
    if t == "entier":
        return int(Decimal(stockee))
    if t in NOMBRES:
        return Decimal(stockee)
    if t == "booleen":
        return stockee == "true"
    if t == "bareme":
        return [
            {"jusqu_a": None if x["jusqu_a"] is None else Decimal(str(x["jusqu_a"])), "taux": Decimal(str(x["taux"]))}
            for x in json.loads(stockee)
        ]
    return stockee


def valeur_en_vigueur(parametre: Parametre, a_la_date: Optional[date] = None) -> Optional[ValeurParametre]:
    jour = a_la_date or date.today()
    for v in parametre.valeurs:  # triées par date d'effet décroissante
        if v.date_effet <= jour:
            return v
    return None


def lire(db: Session, cle: str, a_la_date: Optional[date] = None) -> Any:
    """Valeur typée du paramètre `cle` à la date donnée (aujourd'hui par défaut)."""
    p = db.get(Parametre, cle)
    if p is None:
        raise ParametreIntrouvable(f"Paramètre inconnu : {cle}")
    v = valeur_en_vigueur(p, a_la_date)
    if v is None:
        raise ParametreIntrouvable(f"Aucune valeur en vigueur pour {cle} au {a_la_date or date.today()}")
    return convertir(p, v.valeur)


def a_confirmer(db: Session, a_la_date: Optional[date] = None) -> list[Parametre]:
    """Paramètres dont la valeur en vigueur est encore « à confirmer »."""
    resultat = []
    for p in db.query(Parametre).order_by(Parametre.categorie, Parametre.ordre).all():
        v = valeur_en_vigueur(p, a_la_date)
        if v is not None and v.statut == "a_confirmer":
            resultat.append(p)
    return resultat


def critiques_a_confirmer(db: Session, a_la_date: Optional[date] = None) -> list[Parametre]:
    """À consulter avant de valider un bulletin : ces paramètres rendent le calcul non fiable."""
    return [p for p in a_confirmer(db, a_la_date) if p.critique]
