from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration lue dans l'environnement ou dans backend/.env (jamais versionné)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Base de données (PostgreSQL, une seule base pour tous les exercices) ---
    DATABASE_URL: str

    # --- Sécurité ---
    # Clé de signature des jetons d'accès (cf. core/tokens.py). OBLIGATOIRE, 32 caractères minimum :
    # le serveur refuse de démarrer sinon. Générer avec :
    #   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
    # Changer cette clé déconnecte tout le monde.
    AUTH_SECRET_KEY: str
    # Clé de chiffrement des champs sensibles en base (RIB, numéro CNPS...), cf. core/crypto.py.
    # Générer avec : python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # ATTENTION : la perdre rend ces champs illisibles. Elle doit être sauvegardée à part de la base.
    ENCRYPTION_KEY: str
    # Durée de vie d'une session, en heures.
    AUTH_TOKEN_TTL_HOURS: float = 10
    # Anti force brute sur /auth/login : N échecs consécutifs -> verrouillage M minutes.
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    # Longueur minimale d'un mot de passe.
    PASSWORD_MIN_LENGTH: int = 10

    # --- CORS : origines autorisées à appeler l'API depuis un navigateur, séparées par des virgules.
    # Vide = aucune origine externe (cas normal en production : nginx sert le front et relaie /api).
    CORS_ORIGINS: str = "http://localhost:5178"

    # Environnement : "dev" ou "prod" (influence les avertissements de démarrage).
    APP_ENV: str = "dev"

    @field_validator("AUTH_SECRET_KEY")
    @classmethod
    def _cle_assez_longue(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("AUTH_SECRET_KEY doit faire au moins 32 caractères.")
        return v

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def _cle_chiffrement_valide(cls, v: str) -> str:
        from cryptography.fernet import Fernet

        try:
            Fernet(v.encode("ascii"))
        except Exception as exc:
            raise ValueError("ENCRYPTION_KEY n'est pas une clé Fernet valide (44 caractères base64).") from exc
        return v


settings = Settings()
