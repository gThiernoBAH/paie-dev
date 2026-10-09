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
from . import logo as logo_pdf
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


def _p(db: Session, cle: str, jour, defaut):
    """Réglage de présentation ; la valeur d'origine sert si le paramètre n'existe pas encore (base non migrée)."""
    try:
        return param.lire(db, cle, jour)
    except param.ParametreIntrouvable:
        return defaut


def _texte_libre(valeur) -> str:
    v = (valeur or "").strip()
    return "" if v in ("", "-") else v


def _cumuls(db: Session, b: models.Bulletin, campagne: models.Campagne) -> dict:
    """Cumuls de l'année jusqu'à cette paie incluse (bulletins validés + celui-ci s'il est encore provisoire)."""
    q = db.query(models.Bulletin, models.Campagne).join(models.Campagne, models.Campagne.id == models.Bulletin.campagne_id)\
        .filter(models.Bulletin.salarie_id == b.salarie_id, models.Bulletin.statut == "valide", models.Campagne.annee == campagne.annee)
    lignes = [x for x, c in q.all() if (c.mois, c.numero) <= (campagne.mois, campagne.numero) and x.id != b.id]
    lignes.append(b)
    z = Decimal(0)
    return {"imposable": sum((x.total_imposable for x in lignes), z), "cnps": sum((x.cnps for x in lignes), z),
            "its": sum((x.its for x in lignes), z), "net": sum((x.net_a_payer for x in lignes), z)}


def _page_bulletin(db: Session, b: models.Bulletin, campagne: models.Campagne, entreprise: dict, st) -> list:
    ident = b.identite
    sal = db.get(models.Salarie, b.salarie_id)
    cnps_salarie = crypto.dechiffrer(sal.numero_cnps_chiffre) if sal and sal.numero_cnps_chiffre else ""
    elements = []
    periode = (f"{MOIS[campagne.mois]} {campagne.annee}" if campagne.nature_bulletin == "mensuel"
               else f"du {campagne.debut.strftime('%d/%m/%Y')} au {campagne.fin.strftime('%d/%m/%Y')}")
    bloc_entreprise = Paragraph(f"<b>{entreprise['nom']}</b><br/>{entreprise['adresse']}<br/>N° CNPS employeur : {entreprise['cnps']}<br/>N° contribuable : {entreprise['cc']}", st["petit"])
    jour = campagne.fin
    img = logo_pdf.logo(hauteur_mm=float(_p(db, "bulletin_logo_hauteur_mm", jour, 14)), largeur_max_mm=40)
    tete = Table([[
        [img, Spacer(1, 1 * mm), bloc_entreprise] if img is not None else bloc_entreprise,
        Paragraph(f"<b>BULLETIN DE PAIE</b><br/>{periode}" + ("<br/><font color='#b45309'>PROVISOIRE (non validé)</font>" if b.statut != "valide" else ""), st["titre"]),
    ]], colWidths=[95 * mm, 85 * mm])
    tete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, colors.grey)]))
    elements += [tete, Spacer(1, 3 * mm)]

    def ref(c):
        return (ident.get(c) or {}).get("libelle", "") if ident.get(c) else ""
    P = lambda t: Paragraph(t, st["petit"])
    lignes_identite = [[P(f"<b>Matricule</b> : {ident['matricule']}"), P(f"<b>Nom</b> : {ident['nom']} {ident.get('prenoms') or ''}")]]
    if _p(db, "bulletin_afficher_identite_emploi", jour, True):
        lignes_identite += [[P(f"<b>Emploi</b> : {ref('emploi')}"), P(f"<b>Catégorie</b> : {ref('categorie')}")],
                            [P(f"<b>Service</b> : {ref('service')}"), P(f"<b>Date d'embauche</b> : {(ident.get('date_embauche') or '')[:10]}")]]
    else:
        lignes_identite += [[P(f"<b>Date d'embauche</b> : {(ident.get('date_embauche') or '')[:10]}"), P("")]]
    lignes_identite += [[P(f"<b>Parts fiscales</b> : {_nombre(ident.get('parts'))}"), P(f"<b>N° CNPS</b> : {cnps_salarie}")]]
    identite = Table(lignes_identite, colWidths=[90 * mm, 90 * mm])
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
    elements += [totaux, Spacer(1, 2 * mm), net, Spacer(1, 2 * mm)]
    if _p(db, "bulletin_afficher_net_en_lettres", jour, True):
        elements.append(Paragraph(f"Arrêté le présent bulletin à la somme de : <i>{nombres.montant_en_lettres(int(b.net_a_payer))}</i>", st["petit"]))
    mode = ident.get("mode_paiement")
    if mode and _p(db, "bulletin_afficher_mode_paiement", jour, True):
        elements.append(Paragraph(f"Mode de paiement : {mode}", st["petit"]))

    infos = []
    if _p(db, "bulletin_afficher_cumuls", jour, False):
        c = _cumuls(db, b, campagne)
        infos.append([f"Cumuls {campagne.annee}", f"Imposable {_fcfa(c['imposable'])}", f"CNPS {_fcfa(c['cnps'])}", f"ITS {_fcfa(c['its'])}", f"Net {_fcfa(c['net'])}"])
    if _p(db, "bulletin_afficher_conges", jour, False):
        sal = db.get(models.Salarie, b.salarie_id)
        if sal is not None:
            from ..services import conges as svc_conges
            sd = svc_conges.solde(db, sal, campagne.fin)
            infos.append(["Congés", f"Solde au {campagne.fin.strftime('%d/%m/%Y')} : {_nombre(sd.get('solde'))} jour(s) ouvrable(s)", "", "", ""])
    if _p(db, "bulletin_afficher_charges_patronales", jour, False):
        infos.append(["Charges patronales", _fcfa(b.charges_patronales.get("total", 0)), "", "", ""])
    if infos:
        t = Table(infos, colWidths=[34 * mm, 38 * mm, 34 * mm, 34 * mm, 40 * mm])
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 7.5), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        elements += [Spacer(1, 2 * mm), t]
    elements.append(Spacer(1, 4 * mm))
    mention = _texte_libre(_p(db, "bulletin_mentions_legales", jour, "Conservez ce bulletin sans limitation de durée."))
    if mention:
        elements.append(Paragraph(mention.replace("\n", "<br/>"), st["petit"]))
    pied = _texte_libre(_p(db, "bulletin_pied_de_page", jour, "-"))
    if pied:
        elements.append(Paragraph(pied.replace("\n", "<br/>"), st["petit"]))
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
