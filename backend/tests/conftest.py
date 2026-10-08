"""Fixtures de test : base PostgreSQL jetable, recréée à chaque session de tests.

Variable d'environnement : TEST_DATABASE_URL (défaut : base `paiedb_test` locale, rôle `paie`).
ATTENTION : le schéma `public` de cette base est SUPPRIMÉ puis recréé -- ne jamais la faire pointer
vers une base qui contient des données.
"""
import os
from pathlib import Path

import psycopg2
import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://paie:paie_test_pw@localhost:5432/paiedb_test")
if "test" not in TEST_URL.rsplit("/", 1)[-1]:
    raise RuntimeError("TEST_DATABASE_URL doit viser une base dont le nom contient « test ».")

# Variables lues par app.core.settings : posées AVANT tout import de l'application.
os.environ["DATABASE_URL"] = TEST_URL
os.environ["AUTH_SECRET_KEY"] = "cle-de-test-pour-les-jetons-0123456789-abcdef"
os.environ["ENCRYPTION_KEY"] = "ZmRzYWZkc2FmZHNhZmRzYWZkc2FmZHNhZmRzYWZkc2E="  # clé Fernet de test
os.environ["LOGIN_MAX_ATTEMPTS"] = "3"
os.environ["APP_ENV"] = "test"

SCHEMA = Path(__file__).resolve().parent.parent / "scripts" / "schema.sql"
PARAMS = Path(__file__).resolve().parent.parent / "scripts" / "params.sql"


@pytest.fixture(scope="session", autouse=True)
def base_de_test():
    connexion = psycopg2.connect(TEST_URL)
    connexion.autocommit = True
    with connexion.cursor() as curseur:
        curseur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        curseur.execute(SCHEMA.read_text(encoding="utf-8"))
        curseur.execute(PARAMS.read_text(encoding="utf-8"))
    connexion.close()
    yield


@pytest.fixture(autouse=True)
def base_propre():
    """Vide les tables entre deux tests (TRUNCATE n'est pas bloqué par le trigger d'audit)."""
    from app.core import login_throttle

    login_throttle.reinitialiser_tout()
    connexion = psycopg2.connect(TEST_URL)
    connexion.autocommit = True
    with connexion.cursor() as curseur:
        curseur.execute("TRUNCATE journal_audit, permissions_utilisateurs, utilisateurs RESTART IDENTITY CASCADE")
        # Les paramètres reviennent à leur état initial (params.sql) avant chaque test.
        curseur.execute("TRUNCATE valeurs_parametres, parametres RESTART IDENTITY CASCADE")
        curseur.execute(PARAMS.read_text(encoding="utf-8"))
    connexion.close()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def db():
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def creer_compte(db, identifiant="admin", role="admin", mot_de_passe="MotDePasse2026", doit_changer=False, permissions=()):
    from app.core import auth
    from app.core.models import PermissionUtilisateur, Utilisateur

    user = Utilisateur(
        identifiant=identifiant, nom=identifiant.upper(), role=role,
        mot_de_passe_hash=auth.get_password_hash(mot_de_passe),
        est_actif=True, doit_changer_mot_de_passe=doit_changer,
    )
    user.permissions = [PermissionUtilisateur(permission=p) for p in permissions]
    db.add(user)
    db.commit()
    return user


def connexion(client, identifiant="admin", mot_de_passe="MotDePasse2026"):
    r = client.post("/auth/login", json={"identifiant": identifiant, "password": mot_de_passe})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
