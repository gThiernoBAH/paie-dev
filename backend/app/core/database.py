from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .settings import settings

# Base transactionnelle unique de SIVOP Paie (mono-société : une seule base pour tous les exercices).
# pool_pre_ping + pool_recycle : même protection que vusine-dev contre les connexions que le serveur
# ou un pare-feu a fermées après inactivité ("SSL connection has been closed unexpectedly").
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
