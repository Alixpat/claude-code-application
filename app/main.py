import os
import uuid
import shutil
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="Gestion Budgétaire")

SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory="templates")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://myapp:myapp@db:5432/myapp")
engine = create_engine(DATABASE_URL)

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path("/app/static")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@app.on_event("startup")
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id SERIAL PRIMARY KEY,
                nom VARCHAR(200) NOT NULL,
                email VARCHAR(200) UNIQUE NOT NULL,
                mot_de_passe VARCHAR(200) NOT NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('chef_projet', 'superviseur')),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS demandes_budget (
                id SERIAL PRIMARY KEY,
                utilisateur_id INTEGER REFERENCES utilisateurs(id),
                nom_application VARCHAR(300) NOT NULL,
                montant NUMERIC(12, 2) NOT NULL,
                justification TEXT,
                piece_jointe_nom VARCHAR(500),
                piece_jointe_path VARCHAR(500),
                statut VARCHAR(20) DEFAULT 'en_attente' CHECK (statut IN ('en_attente', 'approuve', 'refuse')),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        # Add mot_de_passe column if it doesn't exist (migration)
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'utilisateurs' AND column_name = 'mot_de_passe'
                ) THEN
                    ALTER TABLE utilisateurs ADD COLUMN mot_de_passe VARCHAR(200) NOT NULL DEFAULT '';
                END IF;
            END $$;
        """))
        # Insert default users if they don't exist
        result = conn.execute(text("SELECT COUNT(*) FROM utilisateurs"))
        if result.scalar() == 0:
            default_pwd = hash_password("budget2026")
            conn.execute(text("""
                INSERT INTO utilisateurs (nom, email, mot_de_passe, role) VALUES
                (:n1, :e1, :p, 'chef_projet'),
                (:n2, :e2, :p, 'chef_projet'),
                (:n3, :e3, :p, 'superviseur')
            """), {
                "n1": "Marie Dupont", "e1": "marie.dupont@gouv.fr",
                "n2": "Pierre Martin", "e2": "pierre.martin@gouv.fr",
                "n3": "Sophie Bernard", "e3": "sophie.bernard@gouv.fr",
                "p": default_pwd,
            })


def get_current_user(request: Request):
    """Retrieve current user from session, or None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    with engine.begin() as conn:
        result = conn.execute(text("SELECT * FROM utilisateurs WHERE id = :id"), {"id": user_id})
        user = result.mappings().first()
    return dict(user) if user else None


def require_auth(request: Request):
    """Dependency that requires authentication."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_role(request: Request, role: str):
    """Check user has the required role."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    if user["role"] != role:
        raise HTTPException(status_code=403, detail="Accès interdit")
    return user


# --- Auth routes ---

@app.get("/", response_class=HTMLResponse)
def accueil(request: Request):
    user = get_current_user(request)
    if user:
        if user["role"] == "chef_projet":
            return RedirectResponse(url="/chef-projet", status_code=303)
        else:
            return RedirectResponse(url="/superviseur", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
    })


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), mot_de_passe: str = Form(...)):
    with engine.begin() as conn:
        result = conn.execute(text(
            "SELECT * FROM utilisateurs WHERE email = :email AND mot_de_passe = :pwd"
        ), {"email": email, "pwd": hash_password(mot_de_passe)})
        user = result.mappings().first()

    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email ou mot de passe incorrect.",
        })

    request.session["user_id"] = user["id"]
    if user["role"] == "chef_projet":
        return RedirectResponse(url="/chef-projet", status_code=303)
    else:
        return RedirectResponse(url="/superviseur", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# --- Chef de projet routes ---

@app.get("/chef-projet", response_class=HTMLResponse)
def dashboard_chef_projet(request: Request):
    utilisateur = require_role(request, "chef_projet")

    with engine.begin() as conn:
        demandes = conn.execute(text("""
            SELECT * FROM demandes_budget WHERE utilisateur_id = :uid ORDER BY created_at DESC
        """), {"uid": utilisateur["id"]})
        demandes_list = [dict(r._mapping) for r in demandes]

    return templates.TemplateResponse("chef_projet.html", {
        "request": request,
        "utilisateur": utilisateur,
        "demandes": demandes_list,
    })


@app.get("/chef-projet/nouvelle-demande", response_class=HTMLResponse)
def form_nouvelle_demande(request: Request):
    utilisateur = require_role(request, "chef_projet")
    return templates.TemplateResponse("nouvelle_demande.html", {
        "request": request,
        "utilisateur": utilisateur,
    })


@app.post("/chef-projet/nouvelle-demande")
async def creer_demande(
    request: Request,
    nom_application: str = Form(...),
    montant: float = Form(...),
    justification: str = Form(""),
    piece_jointe: UploadFile = File(None),
):
    utilisateur = require_role(request, "chef_projet")
    piece_jointe_nom = None
    piece_jointe_path = None

    if piece_jointe and piece_jointe.filename:
        ext = Path(piece_jointe.filename).suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = UPLOAD_DIR / unique_name
        with open(file_path, "wb") as f:
            shutil.copyfileobj(piece_jointe.file, f)
        piece_jointe_nom = piece_jointe.filename
        piece_jointe_path = unique_name

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO demandes_budget (utilisateur_id, nom_application, montant, justification, piece_jointe_nom, piece_jointe_path)
            VALUES (:uid, :nom, :montant, :justif, :pj_nom, :pj_path)
        """), {
            "uid": utilisateur["id"],
            "nom": nom_application,
            "montant": montant,
            "justif": justification,
            "pj_nom": piece_jointe_nom,
            "pj_path": piece_jointe_path,
        })

    return RedirectResponse(url="/chef-projet", status_code=303)


# --- Superviseur routes ---

@app.get("/superviseur", response_class=HTMLResponse)
def dashboard_superviseur(request: Request):
    utilisateur = require_role(request, "superviseur")

    with engine.begin() as conn:
        demandes = conn.execute(text("""
            SELECT d.*, u.nom AS demandeur_nom, u.email AS demandeur_email
            FROM demandes_budget d
            JOIN utilisateurs u ON d.utilisateur_id = u.id
            ORDER BY d.created_at DESC
        """))
        demandes_list = [dict(r._mapping) for r in demandes]

        stats = conn.execute(text("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(montant), 0) AS montant_total,
                COUNT(*) FILTER (WHERE statut = 'en_attente') AS en_attente,
                COUNT(*) FILTER (WHERE statut = 'approuve') AS approuve,
                COUNT(*) FILTER (WHERE statut = 'refuse') AS refuse,
                COALESCE(SUM(montant) FILTER (WHERE statut = 'approuve'), 0) AS montant_approuve,
                COALESCE(SUM(montant) FILTER (WHERE statut = 'en_attente'), 0) AS montant_en_attente
            FROM demandes_budget
        """))
        statistiques = dict(stats.mappings().first())

    return templates.TemplateResponse("superviseur.html", {
        "request": request,
        "utilisateur": utilisateur,
        "demandes": demandes_list,
        "stats": statistiques,
    })


@app.post("/superviseur/decision/{demande_id}")
def decision_demande(request: Request, demande_id: int, statut: str = Form(...)):
    require_role(request, "superviseur")
    if statut not in ("approuve", "refuse"):
        raise HTTPException(status_code=400, detail="Statut invalide")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE demandes_budget SET statut = :statut WHERE id = :id
        """), {"statut": statut, "id": demande_id})
    return RedirectResponse(url="/superviseur", status_code=303)


@app.get("/uploads/{filename}")
def download_file(request: Request, filename: str):
    require_auth(request)
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    return FileResponse(file_path)


@app.get("/version")
def version():
    return {"version": "2.0.0", "status": "budget-management"}
