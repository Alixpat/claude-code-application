# Deploy

Déploie l'application sur une VM via Ansible, déclenché automatiquement à chaque push sur `main`.

## Variables CI/CD à créer sur le GitLab interne

Settings > CI/CD > Variables du dépôt **miroir sur GitLab interne** :

| Variable | Type | Masked | Protected | Valeur |
|---|---|---|---|---|
| `RUNNER_TAG` | Variable | non | non | Tag du runner |
| `ANSIBLE_IMAGE` | Variable | non | non | Image Ansible |
| `SSH_PRIVATE_KEY` | Variable | oui | oui | Clé SSH privée en base64 |
| `SSH_CONFIG` | File | non | oui | Fichier SSH config |
| `INVENTORY` | File | non | oui | Fichier inventory Ansible |

## Déclenchement

- **Automatique** : à chaque push sur `main` (après sync depuis GitHub)
- **Manuel** : CI/CD > Pipelines > Run pipeline
