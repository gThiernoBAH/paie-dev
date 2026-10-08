"""Journal comptable de paie : écritures générées à partir des bulletins validés d'une campagne."""
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from ..core import models
from . import parametres as param

D = Decimal
RETENUES_AVANCES = {"PRE", "ACO"}


def ecritures(db: Session, campagne: models.Campagne) -> list:
    """Écritures équilibrées (débit = crédit) ; les charges sont ventilées par service (colonne analytique)."""
    cp = lambda cle: param.lire(db, cle, campagne.fin)
    debits: dict = defaultdict(lambda: D(0))     # (compte, analytique) -> montant
    credits: dict = defaultdict(lambda: D(0))
    net = D(0)
    for b in db.query(models.Bulletin).filter_by(campagne_id=campagne.id, statut="valide").all():
        serv = ((b.identite.get("service") or {}).get("code")) or ""
        ch = b.charges_patronales
        gi = sum((D(l["montant"]) for l in b.lignes if l["type"] == "GI"), D(0))
        gn = sum((D(l["montant"]) for l in b.lignes if l["type"] == "GN"), D(0))
        ri = sum((D(l["montant"]) for l in b.lignes if l["type"] == "RI"), D(0))
        debits[(cp("compta_compte_remunerations"), serv)] += gi - ri        # les retenues imposables (absences) réduisent la charge
        debits[(cp("compta_compte_indemnites"), serv)] += gn
        cnps_emp = D(ch["retraite"]) + D(ch["prestations_familiales"]) + D(ch["accident_travail"])
        fdfp = D(ch["taxe_apprentissage"]) + D(ch["formation_continue"])
        debits[(cp("compta_compte_charges_cnps"), serv)] += cnps_emp
        debits[(cp("compta_compte_charges_fdfp"), serv)] += fdfp
        credits[(cp("compta_compte_cnps"), "")] += b.cnps + cnps_emp
        credits[(cp("compta_compte_fdfp"), "")] += fdfp
        credits[(cp("compta_compte_its"), "")] += b.its
        for l in b.lignes:
            if l["type"] == "RN":
                m = D(l["montant"])
                if l["code"] in RETENUES_AVANCES:
                    credits[(cp("compta_compte_avances"), "")] += m
                elif l["code"] == "CMU":
                    credits[(cp("compta_compte_cmu"), "")] += m
                else:
                    credits[(cp("compta_compte_retenues_diverses"), "")] += m
        credits[(cp("compta_compte_personnel"), "")] += b.net_a_payer
        net += b.net_a_payer
    ecart = sum(debits.values(), D(0)) - sum(credits.values(), D(0))
    if ecart != 0:
        (credits if ecart > 0 else debits)[(cp("compta_compte_arrondis"), "")] += abs(ecart)
    journal, date_piece = cp("compta_code_journal"), campagne.date_paie or campagne.fin
    piece = f"PAIE{campagne.annee}{campagne.mois:02d}-{campagne.numero}"
    libelle = f"Paie {campagne.libelle}"[:80]
    lignes = []
    for (compte, serv), m in sorted(debits.items()):
        if m:
            lignes.append({"date": date_piece, "journal": journal, "piece": piece, "compte": compte, "libelle": libelle,
                           "debit": m, "credit": D(0), "analytique": serv})
    for (compte, serv), m in sorted(credits.items()):
        if m:
            lignes.append({"date": date_piece, "journal": journal, "piece": piece, "compte": compte, "libelle": libelle,
                           "debit": D(0), "credit": m, "analytique": serv})
    return lignes
