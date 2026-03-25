# Deploy

Déploie l'application **myapp** (FastAPI Hello World) sur une VM via Ansible et Docker Compose, déclenché automatiquement à chaque push sur `main`.

## Architecture

```
VM cible
└── ${DEPLOY_PATH}/        (défaut : /opt/myapp)
    ├── Dockerfile
    ├── docker-compose.yml
    ├── .env               (DOCKER_REGISTRY)
    └── app/
        ├── main.py
        └── requirements.txt
```

Le playbook Ansible :
1. Copie les fichiers sources sur la VM
2. Crée un `.env` avec l'URL du registry Docker interne
3. Lance `docker compose up -d --build --force-recreate`

## Variables CI/CD à créer sur le GitLab interne

Settings > CI/CD > Variables du dépôt **miroir sur GitLab interne** :

| Variable | Type | Masked | Protected | Valeur |
|---|---|---|---|---|
| `RUNNER_TAG` | Variable | non | non | Tag du runner |
| `ANSIBLE_IMAGE` | Variable | non | non | Image Ansible |
| `SSH_PRIVATE_KEY` | Variable | oui | oui | Clé SSH privée en base64 |
| `SSH_CONFIG` | File | non | oui | Fichier SSH config |
| `INVENTORY` | File | non | oui | Fichier inventory Ansible |
| `DOCKER_REGISTRY` | Variable | non | non | URL du registry Docker interne (ex : `registry.internal.example.com`) |
| `DEPLOY_PATH` | Variable | non | non | Chemin de déploiement sur la VM (ex : `/opt/myapp`) |

## Déclenchement

- **Automatique** : à chaque push sur `main` (après sync depuis GitHub)
- **Manuel** : CI/CD > Pipelines > Run pipeline

## Accès à l'application

Une fois déployée, l'application est accessible sur le port **1000** de la VM cible :

```
curl http://<IP_VM>:1000/
# {"message":"Hello World"}
```
