"""Lecture d'un fichier de pointages (CSV) : accepte un export de pointeuse sous deux formes.

  A) une ligne par badgeage :   matricule ; date ; heure
  B) une ligne par jour      :   matricule ; date ; entree ; sortie

Le séparateur (; , tabulation) et les formats de date (AAAA-MM-JJ ou JJ/MM/AAAA) sont détectés. Pour la
forme A, la première heure du jour est l'entrée et la dernière la sortie.
"""
import csv
import io
import re
from datetime import date, datetime, time
from typing import Optional

ALIAS = {
    "matricule": {"matricule", "mat", "id", "badge", "employe", "employé", "no", "numero", "numéro"},
    "date": {"date", "jour"},
    "heure": {"heure", "time", "horaire", "badgeage", "pointage"},
    "entree": {"entree", "entrée", "arrivee", "arrivée", "in", "debut", "début"},
    "sortie": {"sortie", "depart", "départ", "out", "fin"},
}


class FichierInvalide(ValueError):
    pass


def _norm(s: str) -> str:
    return re.sub(r"[^a-zéèàù0-9]", "", s.strip().lower())


def _date(texte: str) -> date:
    texte = texte.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texte[:10] if fmt.startswith("%Y") else texte, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date illisible « {texte} »")


def _heure(texte: str) -> time:
    m = re.fullmatch(r"\s*(\d{1,2})[:hH](\d{2})(?::(\d{2}))?\s*", texte or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError(f"heure illisible « {texte} »")
    return time(int(m.group(1)), int(m.group(2)))


def lire(contenu: str) -> tuple[dict, list, int]:
    """Renvoie ({(matricule, jour): [entree, sortie]}, rejets, nombre de lignes lues)."""
    contenu = contenu.lstrip("﻿")
    if not contenu.strip():
        raise FichierInvalide("Le fichier est vide.")
    echantillon = contenu[:2000]
    delimiteur = max(";,\t", key=echantillon.count)
    lecteur = csv.reader(io.StringIO(contenu), delimiter=delimiteur)
    lignes = [l for l in lecteur if any(c.strip() for c in l)]
    entete = [_norm(c) for c in lignes[0]]
    colonnes = {}
    for cle, noms in ALIAS.items():
        for i, c in enumerate(entete):
            if c in {_norm(n) for n in noms}:
                colonnes.setdefault(cle, i)
    if "matricule" not in colonnes or "date" not in colonnes or not ({"heure"} <= colonnes.keys() or {"entree", "sortie"} <= colonnes.keys()):
        raise FichierInvalide("Colonnes attendues : matricule, date, et soit heure, soit entree + sortie.")

    jours, rejets = {}, []
    for numero, l in enumerate(lignes[1:], start=2):
        try:
            mat = re.sub(r"\D", "", l[colonnes["matricule"]])
            if not mat or len(mat) > 6:
                raise ValueError("matricule illisible")
            mat = mat.zfill(6)
            jour = _date(l[colonnes["date"]])
            if "heure" in colonnes and "entree" not in colonnes:
                heures = [_heure(l[colonnes["heure"]])]
            else:
                heures = [_heure(l[colonnes["entree"]])]
                if l[colonnes["sortie"]].strip():
                    heures.append(_heure(l[colonnes["sortie"]]))
            jours.setdefault((mat, jour), []).extend(heures)
        except (ValueError, IndexError) as e:
            rejets.append({"ligne": numero, "motif": str(e) or "ligne incomplète"})
    resultat = {}
    for cle, hs in jours.items():
        hs = sorted(hs)
        resultat[cle] = [hs[0], hs[-1] if len(hs) > 1 else None]
    return resultat, rejets, len(lignes) - 1
