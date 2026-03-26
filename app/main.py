import os
import uuid
import shutil
import hashlib
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from starlette.middleware.sessions import SessionMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://myapp:myapp@db:5432/myapp")
engine = create_engine(DATABASE_URL)

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path("/app/static")

EXTENSIONS_AUTORISEES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
TAILLE_MAX_UPLOAD = 10 * 1024 * 1024  # 10 Mo


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    sel = "gestion-budgetaire-sel-fixe"
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), sel.encode(), 100_000).hex()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Gestion Budgétaire", lifespan=lifespan)

SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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
        # Ajouter la colonne mot_de_passe si elle n'existe pas (migration)
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
        # Migrer les mots de passe de l'ancien hash (sha256) vers le nouveau (pbkdf2)
        ancien_hash = hashlib.sha256("budget2026".encode()).hexdigest()
        nouveau_hash = hacher_mot_de_passe("budget2026")
        conn.execute(text("""
            UPDATE utilisateurs SET mot_de_passe = :nouveau
            WHERE mot_de_passe = :ancien
        """), {"ancien": ancien_hash, "nouveau": nouveau_hash})

        # Insérer les utilisateurs par défaut s'ils n'existent pas
        result = conn.execute(text("SELECT COUNT(*) FROM utilisateurs"))
        if result.scalar() == 0:
            mdp_defaut = hacher_mot_de_passe("budget2026")
            conn.execute(text("""
                INSERT INTO utilisateurs (nom, email, mot_de_passe, role) VALUES
                (:nom1, :email1, :mdp, 'chef_projet'),
                (:nom2, :email2, :mdp, 'chef_projet'),
                (:nom3, :email3, :mdp, 'superviseur')
            """), {
                "nom1": "Marie Dupont", "email1": "marie.dupont@gouv.fr",
                "nom2": "Pierre Martin", "email2": "pierre.martin@gouv.fr",
                "nom3": "Sophie Bernard", "email3": "sophie.bernard@gouv.fr",
                "mdp": mdp_defaut,
            })
            # Insérer des exemples de demandes pour que l'app soit fonctionnelle au premier déploiement
            conn.execute(text("""
                INSERT INTO demandes_budget
                    (utilisateur_id, nom_application, montant, justification, statut, created_at)
                VALUES
                    (1, 'Portail Usagers v2', 45000.00,
                     'Refonte complète du portail usagers pour mise en conformité RGAA et amélioration de l''expérience utilisateur.',
                     'approuve', '2026-01-15 10:30:00'),
                    (1, 'API DataGouv Connecteur', 12500.00,
                     'Développement d''un connecteur API pour synchroniser les données avec data.gouv.fr.',
                     'en_attente', '2026-02-20 14:00:00'),
                    (1, 'Migration Cloud Sécurisé', 78000.00,
                     'Migration de l''infrastructure vers le cloud SecNumCloud pour conformité hébergement données sensibles.',
                     'en_attente', '2026-03-10 09:15:00'),
                    (2, 'Outil de Reporting Interne', 23000.00,
                     'Tableau de bord de suivi des indicateurs de performance pour la direction.',
                     'refuse', '2026-01-28 11:00:00'),
                    (2, 'Application Mobile Agents', 56000.00,
                     'Application mobile pour les agents terrain permettant la saisie de données en mobilité.',
                     'approuve', '2026-02-05 16:45:00'),
                    (2, 'Système de GED', 34500.00,
                     'Mise en place d''un système de gestion électronique des documents pour dématérialiser les processus.',
                     'en_attente', '2026-03-18 08:30:00'),
                    (1, 'Refonte Intranet Ministériel', 62000.00,
                     'Modernisation de l''intranet avec migration vers une architecture headless CMS et intégration SSO FranceConnect Agent.',
                     'approuve', '2026-01-10 09:00:00'),
                    (1, 'Chatbot Service Public', 18500.00,
                     'Déploiement d''un assistant conversationnel IA pour orienter les usagers dans leurs démarches administratives.',
                     'en_attente', '2026-03-01 11:30:00'),
                    (1, 'Audit Cybersécurité ANSSI', 32000.00,
                     'Réalisation d''un audit complet de sécurité informatique conforme au référentiel ANSSI et tests d''intrusion.',
                     'approuve', '2026-02-12 08:00:00'),
                    (2, 'Plateforme e-Formation', 41000.00,
                     'Création d''une plateforme de formation en ligne pour les agents avec suivi des compétences et certifications.',
                     'en_attente', '2026-02-28 13:45:00'),
                    (2, 'Dématérialisation Marchés Publics', 89000.00,
                     'Développement d''un portail de dématérialisation des marchés publics avec signature électronique intégrée.',
                     'approuve', '2026-01-20 10:00:00'),
                    (2, 'Supervision Infrastructure IT', 15800.00,
                     'Mise en place d''un outil de supervision réseau et applicatif avec alerting temps réel et tableaux de bord.',
                     'refuse', '2026-03-05 15:20:00'),
                    (1, 'Accessibilité RGAA Applications', 27500.00,
                     'Mise en conformité RGAA 4.1 de l''ensemble des applications web du service avec audit et corrections.',
                     'refuse', '2026-02-08 14:30:00'),
                    (1, 'Interconnexion SI Partenaires', 53000.00,
                     'Développement de flux d''échange sécurisés entre le SI interne et les systèmes d''information des partenaires institutionnels.',
                     'en_attente', '2026-03-22 09:45:00'),
                    (2, 'Archivage Numérique Légal', 37500.00,
                     'Mise en place d''un système d''archivage numérique conforme à la norme NF Z42-013 pour la conservation des documents à valeur probante.',
                     'en_attente', '2026-03-15 10:15:00'),
                    (2, 'Outil de Pilotage Budgétaire', 29000.00,
                     'Développement d''un tableau de bord de pilotage budgétaire avec ventilation analytique et prévisions pluriannuelles.',
                     'approuve', '2026-01-05 08:45:00'),
                    (1, 'Modernisation Base de Données', 44000.00,
                     'Migration des bases Oracle vers PostgreSQL avec optimisation des performances et mise en place de la haute disponibilité.',
                     'en_attente', '2026-03-20 11:00:00')
            """))


def obtenir_utilisateur_courant(request: Request):
    """Récupère l'utilisateur courant depuis la session, ou None."""
    utilisateur_id = request.session.get("user_id")
    if not utilisateur_id:
        return None
    with engine.begin() as conn:
        result = conn.execute(text("SELECT * FROM utilisateurs WHERE id = :id"), {"id": utilisateur_id})
        row = result.mappings().first()
    return dict(row) if row else None


def exiger_authentification(request: Request):
    """Vérifie que l'utilisateur est connecté, redirige sinon."""
    utilisateur = obtenir_utilisateur_courant(request)
    if not utilisateur:
        return None
    return utilisateur


def exiger_role(request: Request, role: str):
    """Vérifie que l'utilisateur a le rôle requis."""
    utilisateur = obtenir_utilisateur_courant(request)
    if not utilisateur:
        return None
    if utilisateur["role"] != role:
        raise HTTPException(status_code=403, detail="Accès interdit")
    return utilisateur


# --- Routes d'authentification ---

@app.get("/", response_class=HTMLResponse)
def accueil(request: Request):
    utilisateur = obtenir_utilisateur_courant(request)
    if utilisateur:
        if utilisateur["role"] == "chef_projet":
            return RedirectResponse(url="/chef-projet", status_code=303)
        else:
            return RedirectResponse(url="/superviseur", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def page_connexion(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
    })


@app.post("/login", response_class=HTMLResponse)
def connexion(request: Request, email: str = Form(...), mot_de_passe: str = Form(...)):
    with engine.begin() as conn:
        result = conn.execute(text(
            "SELECT * FROM utilisateurs WHERE email = :email AND mot_de_passe = :mdp"
        ), {"email": email, "mdp": hacher_mot_de_passe(mot_de_passe)})
        utilisateur = result.mappings().first()

    if not utilisateur:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email ou mot de passe incorrect.",
        })

    request.session["user_id"] = utilisateur["id"]
    if utilisateur["role"] == "chef_projet":
        return RedirectResponse(url="/chef-projet", status_code=303)
    else:
        return RedirectResponse(url="/superviseur", status_code=303)


@app.get("/logout")
def deconnexion(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# --- Routes chef de projet ---

@app.get("/chef-projet", response_class=HTMLResponse)
def tableau_de_bord_chef_projet(request: Request):
    utilisateur = exiger_role(request, "chef_projet")
    if not utilisateur:
        return RedirectResponse(url="/login", status_code=303)

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
def formulaire_nouvelle_demande(request: Request):
    utilisateur = exiger_role(request, "chef_projet")
    if not utilisateur:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("nouvelle_demande.html", {
        "request": request,
        "utilisateur": utilisateur,
    })


@app.post("/chef-projet/nouvelle-demande")
def creer_demande(
    request: Request,
    nom_application: str = Form(...),
    montant: float = Form(...),
    justification: str = Form(""),
    piece_jointe: UploadFile = File(None),
):
    utilisateur = exiger_role(request, "chef_projet")
    if not utilisateur:
        return RedirectResponse(url="/login", status_code=303)

    piece_jointe_nom = None
    piece_jointe_path = None

    if piece_jointe and piece_jointe.filename:
        ext = Path(piece_jointe.filename).suffix.lower()
        if ext not in EXTENSIONS_AUTORISEES:
            raise HTTPException(status_code=400, detail=f"Extension '{ext}' non autorisée")
        piece_jointe.file.seek(0, 2)
        taille = piece_jointe.file.tell()
        piece_jointe.file.seek(0)
        if taille > TAILLE_MAX_UPLOAD:
            raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 10 Mo)")
        nom_unique = f"{uuid.uuid4().hex}{ext}"
        chemin_fichier = UPLOAD_DIR / nom_unique
        with open(chemin_fichier, "wb") as f:
            shutil.copyfileobj(piece_jointe.file, f)
        piece_jointe_nom = piece_jointe.filename
        piece_jointe_path = nom_unique

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


# --- Routes superviseur ---

@app.get("/superviseur", response_class=HTMLResponse)
def tableau_de_bord_superviseur(request: Request):
    utilisateur = exiger_role(request, "superviseur")
    if not utilisateur:
        return RedirectResponse(url="/login", status_code=303)

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
def traiter_decision(request: Request, demande_id: int, statut: str = Form(...)):
    utilisateur = exiger_role(request, "superviseur")
    if not utilisateur:
        return RedirectResponse(url="/login", status_code=303)
    if statut not in ("approuve", "refuse"):
        raise HTTPException(status_code=400, detail="Statut invalide")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE demandes_budget SET statut = :statut WHERE id = :id
        """), {"statut": statut, "id": demande_id})
    return RedirectResponse(url="/superviseur", status_code=303)


@app.get("/uploads/{filename}")
def telecharger_fichier(request: Request, filename: str):
    utilisateur = exiger_authentification(request)
    if not utilisateur:
        return RedirectResponse(url="/login", status_code=303)
    chemin_fichier = (UPLOAD_DIR / filename).resolve()
    if not str(chemin_fichier).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Accès interdit")
    if not chemin_fichier.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    return FileResponse(chemin_fichier)


@app.get("/version")
def version():
    return {"version": "2.0.0", "status": "budget-management"}
