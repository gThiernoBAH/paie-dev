"""Bulletin de paie au format PDF (reportlab). Un document par bulletin, ou plusieurs fusionnés."""
from decimal import Decimal
from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..core import crypto, models
from ..services import nombres
from ..services import parametres as param

TOTAUX_COTE_GAINS = {"TIG", "TI", "TNG", "TNI", "NET"}   # lignes de total affichées dans la colonne « Gains »
MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _fcfa(valeur) -> str:
    n = Decimal(str(valeur))
    texte = f"{n:,.2f}".replace(",", " ").replace(".", ",")
    return texte[:-3] if texte.endswith(",00") else texte


def _nombre(valeur) -> str:
    if valeur in (None, ""):
        return ""
    n = Decimal(str(valeur)).normalize()
    return f"{n:f}".replace(".", ",")


def _entete_entreprise(db: Session, campagne: models.Campagne) -> dict:
    return {
        "nom": param.lire(db, "entreprise_raison_sociale", campagne.fin),
        "adresse": param.lire(db, "entreprise_adresse", campagne.fin),
        "cnps": param.lire(db, "entreprise_numero_cnps", campagne.fin),
        "cc": param.lire(db, "entreprise_numero_contribuable", campagne.fin),
    }


def _page_bulletin(db: Session, b: models.Bulletin, campagne: models.Campagne, entreprise: dict, st) -> list:
    ident = b.identite
    sal = db.get(models.Salarie, b.salarie_id)
    cnps_salarie = crypto.dechiffrer(sal.numero_cnps_chiffre) if sal and sal.numero_cnps_chiffre else ""
    elements = []
    periode = (f"{MOIS[campagne.mois]} {campagne.annee}" if campagne.nature_bulletin == "mensuel"
               else f"du {campagne.debut.strftime('%d/%m/%Y')} au {campagne.fin.strftime('%d/%m/%Y')}")
    tete = Table([[
        Paragraph(f"<b>{entreprise['nom']}</b><br/>{entreprise['adresse']}<br/>N° CNPS employeur : {entreprise['cnps']}<br/>N° contribuable : {entreprise['cc']}", st["petit"]),
        Paragraph(f"<b>BULLETIN DE PAIE</b><br/>{periode}" + ("<br/><font color='#b45309'>PROVISOIRE (non validé)</font>" if b.statut != "valide" else ""), st["titre"]),
    ]], colWidths=[95 * mm, 85 * mm])
    tete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, colors.grey)]))
    elements += [tete, Spacer(1, 3 * mm)]

    def ref(c):
        return (ident.get(c) or {}).get("libelle", "") if ident.get(c) else ""
    identite = Table([
        [Paragraph(f"<b>Matricule</b> : {ident['matricule']}", st["petit"]), Paragraph(f"<b>Nom</b> : {ident['nom']} {ident.get('prenoms') or ''}", st["petit"])],
        [Paragraph(f"<b>Emploi</b> : {ref('emploi')}", st["petit"]), Paragraph(f"<b>Catégorie</b> : {ref('categorie')}", st["petit"])],
        [Paragraph(f"<b>Service</b> : {ref('service')}", st["petit"]), Paragraph(f"<b>Date d'embauche</b> : {(ident.get('date_embauche') or '')[:10]}", st["petit"])],
        [Paragraph(f"<b>Parts fiscales</b> : {_nombre(ident.get('parts'))}", st["petit"]), Paragraph(f"<b>N° CNPS</b> : {cnps_salarie}", st["petit"])],
    ], colWidths=[90 * mm, 90 * mm])
    identite.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.grey), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    elements += [identite, Spacer(1, 3 * mm)]

    donnees = [["Code", "Désignation", "Quantité", "Taux", "Gains", "Retenues"]]
    lignes_total = []
    for l in b.lignes:
        if l["type"] == "TO":
            lignes_total.append(len(donnees))
        gain = l["type"] in ("GI", "GN") or (l["type"] == "TO" and l["code"] in TOTAUX_COTE_GAINS)
        montant = _fcfa(l["montant"])
        donnees.append([l["code"], l["libelle"], _nombre(l.get("quantite")), _nombre(l.get("taux")),
                        montant if gain else "", "" if gain else montant])
    table = Table(donnees, colWidths=[16 * mm, 75 * mm, 20 * mm, 18 * mm, 26 * mm, 25 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        *[("FONTNAME", (0, i), (-1, i), "Helvetica-Bold") for i in lignes_total],
        *[("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f3f4f6")) for i in lignes_total],
    ]))
    elements += [table, Spacer(1, 3 * mm)]

    totaux = Table([
        ["Total imposable", _fcfa(b.total_imposable), "CNPS salarié", _fcfa(b.cnps)],
        ["Impôt sur traitements (ITS)", _fcfa(b.its), "Total impôts et cotisations", _fcfa(b.total_impots)],
        ["Gains non imposables", _fcfa(b.gains_non_imposables), "Retenues non imposables", _fcfa(b.retenues_non_imposables)],
    ], colWidths=[50 * mm, 40 * mm, 50 * mm, 40 * mm])
    totaux.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey)]))
    net = Table([[Paragraph("<b>NET À PAYER</b>", st["normal"]), Paragraph(f"<b>{_fcfa(b.net_a_payer)} FCFA</b>", st["droite"])]],
                colWidths=[90 * mm, 90 * mm])
    net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f4f6")), ("BOX", (0, 0), (-1, -1), 0.8, colors.black)]))
    elements += [totaux, Spacer(1, 2 * mm), net, Spacer(1, 2 * mm),
                 Paragraph(f"Arrêté le présent bulletin à la somme de : <i>{nombres.montant_en_lettres(int(b.net_a_payer))}</i>", st["petit"])]
    mode = ident.get("mode_paiement")
    if mode:
        elements.append(Paragraph(f"Mode de paiement : {mode}", st["petit"]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("Conservez ce bulletin sans limitation de durée.", st["petit"]))
    return elements


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "petit": ParagraphStyle("petit", parent=base["Normal"], fontSize=8, leading=10),
        "normal": ParagraphStyle("normal", parent=base["Normal"], fontSize=10),
        "droite": ParagraphStyle("droite", parent=base["Normal"], fontSize=11, alignment=2),
        "titre": ParagraphStyle("titre", parent=base["Normal"], fontSize=11, leading=14, alignment=1),
    }


def generer(db: Session, campagne: models.Campagne, bulletins: Iterable[models.Bulletin]) -> bytes:
    """PDF contenant un bulletin par page (le bulletin tient sur une page A4 ; saut de page entre deux)."""
    from reportlab.platypus import PageBreak

    st = _styles()
    entreprise = _entete_entreprise(db, campagne)
    tampon = BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Bulletins {campagne.libelle}", author=entreprise["nom"])
    elements: list = []
    for i, b in enumerate(bulletins):
        if i:
            elements.append(PageBreak())
        elements += _page_bulletin(db, b, campagne, entreprise, st)
    if not elements:
        elements.append(Paragraph("Aucun bulletin.", st["normal"]))
    doc.build(elements)
    return tampon.getvalue()
