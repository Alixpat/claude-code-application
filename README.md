# Deploy Playbook

Déploie l'application sur une VM via Ansible, déclenché automatiquement à chaque push sur `main`.

Le code est hébergé sur GitHub et synchronisé vers un GitLab interne. Aucune information relative à l'environnement interne n'est présente dans ce dépôt — tout est dans les variables CI/CD GitLab.

## Structure

```
.
├── .gitlab-ci.yml
├── .gitignore
├── ansible.cfg
├── deploy.yaml
└── roles/
    └── deploy/
        └── tasks/
            └── main.yaml
```

## Variables CI/CD à créer sur le GitLab interne

Settings > CI/CD > Variables du dépôt **miroir sur Gitlab interne** :

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
