"""Rôles et permissions de SIVOP Paie.

Même principe que vusine-dev : une clé par capacité, liste blanche (présence = accès). Un compte
de rôle « admin » a toutes les permissions. Les rôles ne fixent que les permissions proposées à la
création du compte ; l'administrateur les ajuste ensuite compte par compte.

Les clés des lots à venir sont déjà déclarées pour que le journal et l'écran des droits restent
stables d'un lot à l'autre ; chaque lot ne protège que les routes qu'il livre.
"""

ROLES = {
    "admin": "Administrateur",
    "paie": "Gestionnaire de paie",
    "direction": "Direction",
    "salarie": "Salarié",
}

PERMISSION_REGISTRY = {
    # --- Lot 0 ---
    "gerer_utilisateurs": "Créer et gérer les comptes et leurs droits",
    "voir_audit": "Consulter le journal d'audit",
    # --- Lot 1 ---
    "gerer_parametres": "Modifier les paramètres légaux et le paramétrage",
    "voir_parametres": "Consulter les paramètres",
    # --- Lot 2 ---
    "voir_salaries": "Consulter la fiche des salariés",
    "modifier_salaries": "Créer et modifier les salariés",
    "voir_donnees_sensibles": "Voir en clair les données sensibles (RIB, CNPS, salaire)",
    # --- Lots 4 à 7 ---
    "gerer_pointages": "Importer et corriger les pointages",
    "lancer_paie": "Lancer le calcul d'une campagne de paie",
    "valider_bulletins": "Valider les bulletins",
    "gerer_virements": "Préparer et lancer les virements",
    "voir_declarations": "Produire les déclarations (CNPS, ITS, DISA)",
    "voir_rapports": "Consulter les rapports et tableaux de bord",
}

PERMISSIONS_PAR_DEFAUT = {
    "admin": list(PERMISSION_REGISTRY),
    "paie": [
        "voir_parametres", "gerer_parametres", "voir_salaries", "modifier_salaries", "gerer_pointages",
        "lancer_paie", "valider_bulletins", "gerer_virements", "voir_declarations", "voir_rapports",
    ],
    "direction": ["voir_parametres", "voir_salaries", "voir_rapports", "voir_declarations", "voir_audit"],
    "salarie": [],
}
