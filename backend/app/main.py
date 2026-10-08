import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin_routes import router as admin_router
from app.api.auth_routes import router as auth_router
from app.api.campagnes_routes import router as campagnes_router
from app.api.conges_routes import router as conges_router
from app.api.declarations_routes import router as declarations_router
from app.api.virements_routes import router as virements_router
from app.api.parametres_routes import router as parametres_router
from app.api.pointages_routes import router as pointages_router
from app.api.referentiels_routes import router as referentiels_router
from app.api.salaries_routes import router as salaries_router
from app.core.database import engine
from app.core.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s : %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="SIVOP Paie API")

_cors_origines = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if "*" in _cors_origines:
    logger.warning("[SÉCURITÉ] CORS ouvert à toutes les origines (CORS_ORIGINS='*') : à restreindre hors développement.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origines,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def en_tetes_securite(request, call_next):
    reponse = await call_next(request)
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["X-Frame-Options"] = "DENY"
    reponse.headers["Referrer-Policy"] = "same-origin"
    reponse.headers["Cache-Control"] = "no-store"
    return reponse


@app.get("/health", tags=["Santé"])
def health():
    """Contrôle de vie (sans authentification, sans donnée) : l'API répond et la base aussi."""
    with engine.connect() as connexion:
        connexion.execute(text("SELECT 1"))
    return {"statut": "ok"}


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(parametres_router)
app.include_router(referentiels_router)
app.include_router(salaries_router)
app.include_router(pointages_router)
app.include_router(campagnes_router)
app.include_router(conges_router)
app.include_router(declarations_router)
app.include_router(virements_router)
