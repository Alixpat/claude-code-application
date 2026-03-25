import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text

app = FastAPI(title="Gestion Budgétaire")
templates = Jinja2Templates(directory="templates")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://myapp:myapp@db:5432/myapp")
engine = create_engine(DATABASE_URL)

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.on_event("startup")
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id SERIAL PRIMARY KEY,
                nom VARCHAR(200) NOT NULL,
                email VARCHAR(200) UNIQUE NOT NULL,
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
        # Insert default users if they don't exist
        result = conn.execute(text("SELECT COUNT(*) FROM utilisateurs"))
        if result.scalar() == 0:
            conn.execute(text("""
                INSERT INTO utilisateurs (nom, email, role) VALUES
                ('Marie Dupont', 'marie.dupont@gouv.fr', 'chef_projet'),
                ('Pierre Martin', 'pierre.martin@gouv.fr', 'chef_projet'),
                ('Sophie Bernard', 'sophie.bernard@gouv.fr', 'superviseur')
            """))


@app.get("/", response_class=HTMLResponse)
def accueil(request: Request):
    with engine.begin() as conn:
        result = conn.execute(text("SELECT id, nom, email, role FROM utilisateurs ORDER BY role, nom"))
        utilisateurs = [dict(r._mapping) for r in result]
    return templates.TemplateResponse("accueil.html", {
        "request": request,
        "utilisateurs": utilisateurs,
    })


@app.get("/chef-projet/{user_id}", response_class=HTMLResponse)
def dashboard_chef_projet(request: Request, user_id: int):
    with engine.begin() as conn:
        user = conn.execute(text("SELECT * FROM utilisateurs WHERE id = :id AND role = 'chef_projet'"), {"id": user_id})
        utilisateur = user.mappings().first()
        if not utilisateur:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        demandes = conn.execute(text("""
            SELECT * FROM demandes_budget WHERE utilisateur_id = :uid ORDER BY created_at DESC
        """), {"uid": user_id})
        demandes_list = [dict(r._mapping) for r in demandes]

    return templates.TemplateResponse("chef_projet.html", {
        "request": request,
        "utilisateur": dict(utilisateur),
        "demandes": demandes_list,
    })


@app.get("/chef-projet/{user_id}/nouvelle-demande", response_class=HTMLResponse)
def form_nouvelle_demande(request: Request, user_id: int):
    with engine.begin() as conn:
        user = conn.execute(text("SELECT * FROM utilisateurs WHERE id = :id AND role = 'chef_projet'"), {"id": user_id})
        utilisateur = user.mappings().first()
        if not utilisateur:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    return templates.TemplateResponse("nouvelle_demande.html", {
        "request": request,
        "utilisateur": dict(utilisateur),
    })


@app.post("/chef-projet/{user_id}/nouvelle-demande")
async def creer_demande(
    user_id: int,
    nom_application: str = Form(...),
    montant: float = Form(...),
    justification: str = Form(""),
    piece_jointe: UploadFile = File(None),
):
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
            "uid": user_id,
            "nom": nom_application,
            "montant": montant,
            "justif": justification,
            "pj_nom": piece_jointe_nom,
            "pj_path": piece_jointe_path,
        })

    return RedirectResponse(url=f"/chef-projet/{user_id}", status_code=303)


@app.get("/superviseur/{user_id}", response_class=HTMLResponse)
def dashboard_superviseur(request: Request, user_id: int):
    with engine.begin() as conn:
        user = conn.execute(text("SELECT * FROM utilisateurs WHERE id = :id AND role = 'superviseur'"), {"id": user_id})
        utilisateur = user.mappings().first()
        if not utilisateur:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

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
        "utilisateur": dict(utilisateur),
        "demandes": demandes_list,
        "stats": statistiques,
    })


@app.post("/superviseur/{user_id}/decision/{demande_id}")
def decision_demande(user_id: int, demande_id: int, statut: str = Form(...)):
    if statut not in ("approuve", "refuse"):
        raise HTTPException(status_code=400, detail="Statut invalide")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE demandes_budget SET statut = :statut WHERE id = :id
        """), {"statut": statut, "id": demande_id})
    return RedirectResponse(url=f"/superviseur/{user_id}", status_code=303)


@app.get("/uploads/{filename}")
def download_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    return FileResponse(file_path)


@app.get("/version")
def version():
    return {"version": "2.0.0", "status": "budget-management"}
