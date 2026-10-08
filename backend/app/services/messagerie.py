"""Envoi d'e-mails : bulletins aux salariés, alerte au lancement d'un virement.

Réglages dans Paramétrage → E-mail (hôte, port, expéditeur, modèles) ; seul le mot de passe SMTP est dans
l'environnement (SMTP_PASSWORD). Tant que `email_actif` est faux, rien ne part : les envois sont enregistrés
avec le statut « désactivé » pour que l'on voie ce qui serait parti.
"""
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from io import BytesIO
from typing import Optional

from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import Session

from ..core import models
from ..core.settings import settings
from ..exports import bulletin_pdf
from . import parametres as param

VIDES = {"", "-", "à renseigner"}


def _texte(v) -> str:
    return "" if v is None or str(v).strip().lower() in VIDES else str(v).strip()


def configuration(db: Session) -> dict:
    lire = lambda cle: param.lire(db, cle)
    return {
        "actif": bool(lire("email_actif")), "hote": _texte(lire("email_smtp_hote")), "port": int(lire("email_smtp_port")),
        "securite": _texte(lire("email_smtp_securite")) or "starttls", "utilisateur": _texte(lire("email_smtp_utilisateur")),
        "expediteur": _texte(lire("email_expediteur_adresse")), "expediteur_nom": _texte(lire("email_expediteur_nom")),
        "objet_bulletin": str(lire("email_objet_bulletin")), "corps_bulletin": str(lire("email_corps_bulletin")).replace("\\n", "\n"),
        "pdf_protege": bool(lire("email_pdf_protege")),
        "alerte_actif": bool(lire("email_alerte_virement_actif")),
        "alerte_destinataires": [a.strip() for a in _texte(lire("email_alerte_virement_destinataires")).split(",") if a.strip()],
    }


def _smtp_envoyer(cfg: dict, message: EmailMessage) -> None:
    """Point unique d'accès au réseau (remplacé dans les tests)."""
    if not cfg["hote"] or not cfg["expediteur"]:
        raise RuntimeError("Serveur SMTP ou adresse d'expédition non renseigné.")
    contexte = ssl.create_default_context()
    if cfg["securite"] == "ssl":
        serveur = smtplib.SMTP_SSL(cfg["hote"], cfg["port"], timeout=30, context=contexte)
    else:
        serveur = smtplib.SMTP(cfg["hote"], cfg["port"], timeout=30)
    with serveur:
        if cfg["securite"] == "starttls":
            serveur.starttls(context=contexte)
        if cfg["utilisateur"]:
            serveur.login(cfg["utilisateur"], settings.SMTP_PASSWORD)
        serveur.send_message(message)


def _message(cfg: dict, destinataires: list, objet: str, corps: str, pieces: list) -> EmailMessage:
    m = EmailMessage()
    m["From"] = f"{cfg['expediteur_nom']} <{cfg['expediteur']}>" if cfg["expediteur_nom"] else cfg["expediteur"]
    m["To"] = ", ".join(destinataires)
    m["Subject"] = objet
    m.set_content(corps)
    for nom, contenu, type_mime in pieces:
        maintype, subtype = type_mime.split("/")
        m.add_attachment(contenu, maintype=maintype, subtype=subtype, filename=nom)
    return m


def _remplir(modele: str, **valeurs) -> str:
    class _Sur(dict):
        def __missing__(self, k):
            return "{" + k + "}"
    return modele.format_map(_Sur(**valeurs))


def _envoyer(db: Session, n: models.Notification, cfg: dict, destinataires: list, corps: str, pieces: list) -> None:
    """Envoie et met à jour la notification ; ne lève jamais."""
    if not cfg["actif"]:
        n.statut, n.erreur = "desactive", "Envoi d'e-mails désactivé (Paramétrage → E-mail)."
        return
    n.tentatives = (n.tentatives or 0) + 1
    try:
        _smtp_envoyer(cfg, _message(cfg, destinataires, n.objet, corps, pieces))
        n.statut, n.erreur, n.envoye_le = "envoye", None, datetime.now(timezone.utc)
    except Exception as e:  # réseau, authentification, adresse refusée...
        n.statut, n.erreur = "echec", (f"{type(e).__name__}: {e}")[:290]


# ----------------------------------------------------------------- bulletins
def proteger_pdf(contenu: bytes, mot_de_passe: str) -> bytes:
    w = PdfWriter(clone_from=PdfReader(BytesIO(contenu)))
    w.encrypt(mot_de_passe, algorithm="AES-256")
    sortie = BytesIO()
    w.write(sortie)
    return sortie.getvalue()


def mot_de_passe_bulletin(s: models.Salarie) -> Optional[str]:
    return s.date_naissance.strftime("%d%m%Y") if s.date_naissance else None


def periode_libelle(c: models.Campagne) -> str:
    mois = bulletin_pdf.MOIS[c.mois]
    return f"{mois} {c.annee}" if c.nature_bulletin == "mensuel" and c.numero == 1 else f"{c.debut.strftime('%d/%m')} au {c.fin.strftime('%d/%m/%Y')}"


def preparer_envoi_bulletins(db: Session, campagne: models.Campagne, acteur: models.Utilisateur, renvoyer: bool = False) -> dict:
    """Crée les notifications (une par bulletin validé) ; celles qui ne peuvent pas partir sont classées « ignoré »."""
    cfg = configuration(db)
    resume = {"en_attente": 0, "ignores": 0, "deja_envoyes": 0}
    for b in db.query(models.Bulletin).filter_by(campagne_id=campagne.id, statut="valide").order_by(models.Bulletin.id).all():
        s = db.get(models.Salarie, b.salarie_id)
        if b.envoye_le and not renvoyer:
            resume["deja_envoyes"] += 1
            continue
        objet = _remplir(cfg["objet_bulletin"], periode=periode_libelle(campagne), prenom=s.prenoms or "", nom=s.nom, matricule=s.matricule)
        n = models.Notification(type_notif="bulletin", destinataire=s.email, objet=objet[:200], campagne_id=campagne.id,
                                bulletin_id=b.id, cree_par=acteur.identifiant)
        if not s.email:
            n.statut, n.erreur = "ignore", "Pas d'adresse e-mail sur la fiche."
        elif cfg["pdf_protege"] and not mot_de_passe_bulletin(s):
            n.statut, n.erreur = "ignore", "Date de naissance manquante : impossible de protéger le PDF."
        db.add(n)
        resume["ignores" if n.statut == "ignore" else "en_attente"] += 1
    db.flush()
    return resume


def traiter_en_attente(db: Session, campagne_id: int) -> dict:
    cfg = configuration(db)
    campagne = db.get(models.Campagne, campagne_id)
    res = {"envoyes": 0, "echecs": 0, "desactives": 0}
    for n in db.query(models.Notification).filter_by(campagne_id=campagne_id, type_notif="bulletin", statut="en_attente").order_by(models.Notification.id).all():
        b = db.get(models.Bulletin, n.bulletin_id)
        s = db.get(models.Salarie, b.salarie_id)
        if not cfg["actif"]:
            _envoyer(db, n, cfg, [], "", [])
        else:
            pdf = bulletin_pdf.generer(db, campagne, [b])
            if cfg["pdf_protege"]:
                pdf = proteger_pdf(pdf, mot_de_passe_bulletin(s))
            corps = _remplir(cfg["corps_bulletin"], periode=periode_libelle(campagne), prenom=s.prenoms or s.nom, nom=s.nom, matricule=s.matricule)
            _envoyer(db, n, cfg, [s.email], corps, [(f"bulletin_{s.matricule}_{campagne.annee}{campagne.mois:02d}.pdf", pdf, "application/pdf")])
            if n.statut == "envoye":
                b.envoye_le = n.envoye_le
        res[{"envoye": "envoyes", "echec": "echecs", "desactive": "desactives"}[n.statut]] += 1
        db.commit()
    return res


def renvoyer(db: Session, n: models.Notification) -> None:
    if n.statut not in ("echec", "desactive"):
        raise ValueError("Seul un envoi en échec ou désactivé peut être relancé.")
    n.statut = "en_attente"
    db.flush()


# ----------------------------------------------------------------- alerte virement
def alerter_virement(db: Session, lot: models.LotVirement, acteur: models.Utilisateur) -> int:
    """Prévient les destinataires configurés qu'un virement vient d'être lancé. Ne bloque jamais le virement."""
    cfg = configuration(db)
    if not cfg["alerte_actif"] or not cfg["alerte_destinataires"]:
        return 0
    objet = f"Virement de paie lancé – {lot.total:,.0f} FCFA".replace(",", " ")
    corps = (f"Un virement de paie vient d'être lancé.\n\nLot : {lot.libelle}\nOrdres : {lot.nombre_ordres}\n"
             f"Montant total : {lot.total:,.0f} FCFA\nLancé par : {acteur.identifiant}\n"
             f"Date : {lot.lance_le.strftime('%d/%m/%Y %H:%M') if lot.lance_le else ''}\n\n"
             "Si vous n'êtes pas à l'origine de cette opération, contactez immédiatement l'administrateur.").replace(",", " ")
    n = models.Notification(type_notif="alerte_virement", destinataire=", ".join(cfg["alerte_destinataires"])[:200], objet=objet[:200],
                            campagne_id=lot.campagne_id, cree_par=acteur.identifiant)
    db.add(n)
    _envoyer(db, n, cfg, cfg["alerte_destinataires"], corps, [])
    db.commit()
    return 1


def envoyer_test(db: Session, destinataire: str, acteur: models.Utilisateur) -> models.Notification:
    cfg = configuration(db)
    n = models.Notification(type_notif="test", destinataire=destinataire, objet="Test d'envoi – SIVOP Paie", cree_par=acteur.identifiant)
    db.add(n)
    _envoyer(db, n, cfg, [destinataire], "Ceci est un message de test envoyé depuis SIVOP Paie. Si vous le lisez, la configuration e-mail fonctionne.", [])
    db.commit()
    return n
