# Gestion Budgétaire

Application de gestion des demandes de budget, avec un workflow de validation par rôle.

## Fonctionnalités

- **Chef de projet** : soumet des demandes de budget (nom d'application, montant, justification, pièce jointe) et suit leur état
- **Superviseur** : consulte l'ensemble des demandes, les approuve ou les refuse, et visualise des statistiques consolidées (budget total, répartition par statut)
- Authentification par session avec hachage des mots de passe
- Upload et téléchargement de pièces jointes

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Base de données | PostgreSQL 16 |
| ORM | SQLAlchemy 2 |
| Templates | Jinja2 |
| Design system | DSFR v1.12.1 (Système de Design de l'État) |
| Conteneurisation | Docker + Docker Compose |

## Démarrage rapide

```bash
docker compose up -d --build
```

L'application est accessible sur **http://localhost:1000**.

### Comptes de démonstration

| Rôle | Email | Mot de passe |
|---|---|---|
| Chef de projet | `marie.dupont@gouv.fr` | `budget2026` |
| Chef de projet | `pierre.martin@gouv.fr` | `budget2026` |
| Superviseur | `sophie.bernard@gouv.fr` | `budget2026` |

## Structure du projet

```
app/
├── main.py              # Application FastAPI (routes, modèles, auth)
├── requirements.txt     # Dépendances Python
├── templates/           # Templates Jinja2 (login, dashboards, formulaire)
└── static/dsfr/         # Assets DSFR (CSS, JS, polices, icônes)
Dockerfile
docker-compose.yml       # Services : app (port 1000) + db (PostgreSQL)
.deploy/                 # Déploiement Ansible (voir .deploy/README.md)
.gitlab-ci.yml           # Pipeline CI/CD GitLab
```

## Variables d'environnement

| Variable | Description | Défaut |
|---|---|---|
| `SECRET_KEY` | Clé de chiffrement des sessions | Générée aléatoirement |
| `DATABASE_URL` | URL de connexion PostgreSQL | `postgresql://myapp:myapp@db:5432/myapp` |

## API

| Endpoint | Description |
|---|---|
| `/login` | Authentification |
| `/chef-projet` | Tableau de bord chef de projet |
| `/chef-projet/nouvelle-demande` | Soumission d'une demande |
| `/superviseur` | Tableau de bord superviseur |
| `/version` | Version de l'application |
