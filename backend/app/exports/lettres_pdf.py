"""Lettres PDF : virement de salaires (une par banque) et décisions disciplinaires / notes de service."""
from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session
from xml.sax.saxutils import escape

from ..core import crypto, models
from ..services import nombres
from . import logo as logo_pdf
from ..services import parametres as param

MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def date_fr(d: date) -> str:
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month]} {d.year}"


def _fcfa(v) -> str:
    return f"{Decimal(str(v)):,.0f}".replace(",", " ")


def _st() -> dict:
    b = getSampleStyleSheet()
    return {
        "n": ParagraphStyle("n", parent=b["Normal"], fontSize=10.5, leading=15),
        "g": ParagraphStyle("g", parent=b["Normal"], fontSize=12, leading=16, fontName="Helvetica-Bold"),
        "d": ParagraphStyle("d", parent=b["Normal"], fontSize=10.5, leading=15, alignment=2),
        "c": ParagraphStyle("c", parent=b["Normal"], fontSize=13, leading=17, fontName="Helvetica-Bold", alignment=1),
        "p": ParagraphStyle("p", parent=b["Normal"], fontSize=8, leading=10, textColor=colors.grey),
    }


def _entreprise(db: Session, a_date: date) -> dict:
    return {k: param.lire(db, f"entreprise_{k}", a_date) for k in ("raison_sociale", "adresse", "ville", "signataire", "compte_debiteur")}


def _doc(titre: str, auteur: str) -> tuple[BytesIO, SimpleDocTemplate]:
    t = BytesIO()
    return t, SimpleDocTemplate(t, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                                title=titre, author=auteur)


def _entete(e: dict, st: dict, lieu_date: str) -> list:
    img = logo_pdf.logo()
    avant = [img, Spacer(1, 3 * mm)] if img is not None else []
    return avant + [Paragraph(f"<b>{escape(e['raison_sociale'])}</b><br/>{escape(e['adresse'])}", st["n"]), Spacer(1, 8 * mm),
            Paragraph(escape(lieu_date), st["d"]), Spacer(1, 8 * mm)]


def _signature(e: dict, st: dict) -> list:
    return [Spacer(1, 10 * mm), Paragraph(escape(e["signataire"]), st["d"]), Spacer(1, 18 * mm)]


# ------------------------------------------------------------------ virement
def lettres_virement(db: Session, lot: models.LotVirement, campagne: models.Campagne, aujourdhui: date) -> bytes:
    """Une page par banque : ordre de virement groupé avec le détail des bénéficiaires (RIB en clair)."""
    st, e = _st(), _entreprise(db, campagne.fin)
    motif = f"salaires {MOIS[campagne.mois]} {campagne.annee}" + (f" (n°{campagne.numero})" if campagne.numero > 1 else "")
    parbanque: dict[str, list[models.OrdreVirement]] = {}
    for o in lot.ordres:
        parbanque.setdefault(o.banque or "Banque non renseignée", []).append(o)
    tampon, doc = _doc(f"Lettres de virement {lot.libelle}", e["raison_sociale"])
    el: list = []
    for i, (banque, ordres) in enumerate(sorted(parbanque.items())):
        if i:
            el.append(PageBreak())
        total = sum((o.montant for o in ordres), Decimal(0))
        el += _entete(e, st, f"{e['ville']}, le {date_fr(aujourdhui)}")
        el += [Paragraph(f"À Monsieur le Directeur<br/><b>{escape(banque)}</b>", st["n"]), Spacer(1, 8 * mm),
               Paragraph(f"<b>Objet : ordre de virement groupé — {escape(motif)}</b>", st["n"]), Spacer(1, 5 * mm),
               Paragraph("Monsieur le Directeur,", st["n"]), Spacer(1, 3 * mm),
               Paragraph(f"Nous vous prions de bien vouloir débiter notre compte n° <b>{escape(e['compte_debiteur'])}</b> de la somme de "
                         f"<b>{_fcfa(total)} FCFA</b> ({escape(nombres.montant_en_lettres(total))}) et de créditer, "
                         f"{('à la date de valeur du ' + date_fr(lot.date_valeur) + ', ') if lot.date_valeur else ''}"
                         f"les comptes des bénéficiaires ci-dessous, au titre des {escape(motif)}.", st["n"]), Spacer(1, 5 * mm)]
        lignes = [["Matricule", "Bénéficiaire", "RIB", "Montant (FCFA)"]]
        for o in sorted(ordres, key=lambda x: x.salarie.matricule):
            s = o.salarie
            lignes.append([s.matricule, f"{s.nom} {s.prenoms or ''}".strip(), crypto.dechiffrer(o.rib_chiffre), _fcfa(o.montant)])
        lignes.append(["", "TOTAL", f"{len(ordres)} virement(s)", _fcfa(total)])
        t = Table(lignes, colWidths=[22 * mm, 62 * mm, 55 * mm, 31 * mm], repeatRows=1)
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                               ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F1EC")),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        el += [t, Spacer(1, 6 * mm), Paragraph("Veuillez agréer, Monsieur le Directeur, l'expression de nos salutations distinguées.", st["n"])]
        el += _signature(e, st)
    if not el:
        el.append(Paragraph("Aucun ordre de virement.", st["n"]))
    doc.build(el)
    return tampon.getvalue()


# ------------------------------------------------------------------ discipline
_INTRO = {
    "avertissement": ("AVERTISSEMENT", "Nous avons le regret de constater les faits suivants :", "Nous vous adressons par la présente un avertissement. Nous vous invitons à vous conformer strictement à vos obligations professionnelles ; en cas de récidive, une sanction plus sévère pourrait être envisagée."),
    "blame": ("BLÂME", "Nous avons le regret de constater les faits suivants :", "Ces faits constituent un manquement à vos obligations professionnelles ; nous vous notifions par la présente un blâme, qui sera versé à votre dossier."),
    "mise_a_pied": ("MISE À PIED", "Nous avons le regret de constater les faits suivants :", None),
}


def lettre_mesure(db: Session, m: models.MesureDisciplinaire) -> bytes:
    st, e = _st(), _entreprise(db, m.date_decision)
    s = m.salarie
    titre, intro, conclusion = _INTRO[m.type_mesure]
    if conclusion is None:
        conclusion = (f"En conséquence, vous êtes mis(e) à pied sans solde du <b>{date_fr(m.debut_mise_a_pied)}</b> au "
                      f"<b>{date_fr(m.fin_mise_a_pied)}</b> inclus. Cette période d'absence ne sera pas rémunérée. "
                      "Vous reprendrez votre poste à l'issue de cette période.")
    tampon, doc = _doc(f"{titre} {m.reference}", e["raison_sociale"])
    el = _entete(e, st, f"{e['ville']}, le {date_fr(m.date_decision)}")
    el += [Paragraph(f"<b>Réf. : {escape(m.reference or '')}</b>", st["n"]), Spacer(1, 4 * mm),
           Paragraph(f"À {escape(s.nom)} {escape(s.prenoms or '')}<br/>Matricule {escape(s.matricule)}", st["n"]), Spacer(1, 8 * mm),
           Paragraph(f"<b>Objet : notification de {titre.lower()}</b>", st["n"]), Spacer(1, 5 * mm),
           Paragraph(escape(intro), st["n"]), Spacer(1, 2 * mm)]
    if m.date_faits:
        el.append(Paragraph(f"Faits du {date_fr(m.date_faits)} :", st["n"]))
    el += [Paragraph(escape(m.motif).replace("\n", "<br/>"), st["n"]), Spacer(1, 4 * mm), Paragraph(conclusion, st["n"])]
    el += _signature(e, st)
    el += [Paragraph("Reçu en main propre le : ____ / ____ / ________      Signature du salarié : ________________", st["n"]), Spacer(1, 6 * mm),
           Paragraph("Modèle de lettre à faire valider par le service juridique avant usage.", st["p"])]
    doc.build(el)
    return tampon.getvalue()


def note_de_service(db: Session, n: models.NoteService) -> bytes:
    st, e = _st(), _entreprise(db, n.date_effet)
    tampon, doc = _doc(f"Note de service {n.reference}", e["raison_sociale"])
    dest = n.service.libelle if n.service else "Tout le personnel"
    el = _entete(e, st, f"{e['ville']}, le {date_fr(n.date_effet)}")
    el += [Paragraph("NOTE DE SERVICE", st["c"]), Paragraph(f"<para alignment='center'>{escape(n.reference or '')}</para>", st["n"]),
           Spacer(1, 6 * mm), Paragraph(f"<b>Destinataires :</b> {escape(dest)}", st["n"]),
           Paragraph(f"<b>Objet :</b> {escape(n.objet)}", st["n"]), Spacer(1, 6 * mm),
           Paragraph(escape(n.contenu).replace("\n", "<br/>"), st["n"])]
    el += _signature(e, st)
    doc.build(el)
    return tampon.getvalue()
