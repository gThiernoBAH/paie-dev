"""Moteur de calcul de la paie : fonctions pures, sans base de données ni réseau.

Les règles légales n'y sont jamais codées en dur : elles arrivent dans un objet `ParametresPaie`
construit par `parametres_paie.charger(db, date)` à partir des paramètres datés. Le même calcul
refait avec les mêmes entrées et les mêmes paramètres redonne toujours le même bulletin.
"""
