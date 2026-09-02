# Installation et exploitation sur Raspberry Pi

## 1. Objectif

Ce guide décrit une installation complète sur une Raspberry Pi vide, depuis Raspberry Pi OS jusqu'à la synchronisation Garmin, PostgreSQL, l'API coach et la génération Excel.

Les commandes supposent :

- Raspberry Pi OS Lite 64 bits ou Debian 13 Trixie ARM64 ;
- utilisateur SSH `es40` à adapter si nécessaire ;
- dépôt installé dans `/opt/sport` ;
- accès Internet fonctionnel ;
- compte Garmin Connect existant.

## 2. Préparer le système

### 2.1 Vérifier la machine

```bash
cat /etc/os-release
uname -m
dpkg --print-architecture
free -h
lsblk
df -h /
ip -br addr
ip route
timedatectl
vcgencmd measure_temp
vcgencmd get_throttled
```

Résultats attendus :

- architecture `aarch64` et `arm64` ;
- horloge synchronisée ;
- température normale ;
- `throttled=0x0` ;
- stockage disponible suffisant.

Un SSD USB de 64 Go ou plus est recommandé pour PostgreSQL et les données à long terme. Les sauvegardes doivent être placées sur un autre support.

### 2.2 Réseau

Vérifier Internet et le DNS :

```bash
ping -c 3 1.1.1.1
ping -c 3 deb.debian.org
ip route get 1.1.1.1
```

Pour un serveur permanent, préférer Ethernet et une réservation DHCP configurée dans la box. Éviter une adresse statique improvisée sur la Pi.

### 2.3 Mettre le système à jour

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt autoremove -y
sudo apt clean
sudo timedatectl set-timezone Europe/Paris
sudo reboot
```

Se reconnecter en SSH après le redémarrage.

## 3. Installer Docker Engine et Compose

Docker prend officiellement en charge Debian 13 Trixie et ARM64. Utiliser le dépôt officiel : https://docs.docker.com/engine/install/debian/

### 3.1 Installer les prérequis

```bash
sudo apt update
sudo apt install -y ca-certificates curl git openssl
```

### 3.2 Ajouter la clé et le dépôt Docker

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

```bash
sudo apt update
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

### 3.3 Vérifier Docker

```bash
sudo systemctl status docker --no-pager
sudo docker run --rm hello-world
docker --version
sudo docker compose version
```

### 3.4 Autoriser l'utilisateur courant

```bash
sudo usermod -aG docker "$USER"
exit
```

Se reconnecter puis tester sans `sudo` :

```bash
docker run --rm hello-world
docker compose version
```

Attention : le groupe `docker` donne des privilèges administratifs élevés.

## 4. Cloner le dépôt

Remplacer `<URL_DU_DEPOT_GIT>` par l'adresse réelle :

```bash
sudo mkdir -p /opt/sport
sudo chown "$USER":"$USER" /opt/sport
git clone <URL_DU_DEPOT_GIT> /opt/sport
cd /opt/sport
```

Pour un dépôt privé, utiliser une clé SSH Git ou un jeton d'accès selon l'hébergeur. Ne jamais placer le jeton dans les fichiers du projet.

## 5. Créer les dossiers persistants

```bash
cd /opt/sport
mkdir -p garmin-tokens data/activities exports backups
chmod 700 garmin-tokens
```

Les montages attendus dans `compose.yaml` sont :

```yaml
volumes:
  - ./backend/alembic:/app/alembic
  - ./garmin-tokens:/var/lib/sport/garmin
  - ./data:/var/lib/sport/data
  - ./exports:/var/lib/sport/exports
```

PostgreSQL doit utiliser le volume nommé :

```yaml
volumes:
  sport_postgres_data:
```

## 6. Configurer les secrets

### 6.1 Générer les valeurs

Générer un mot de passe PostgreSQL et une clé coach distincts :

```bash
openssl rand -hex 24
openssl rand -hex 32
```

Ne pas publier les résultats.

### 6.2 Créer `.env`

```bash
cd /opt/sport
cp .env.example .env
chmod 600 .env
nano .env
```

Exemple :

```env
POSTGRES_DB=sport
POSTGRES_USER=sport
POSTGRES_PASSWORD=REMPLACER_PAR_LE_MOT_DE_PASSE
DATABASE_URL=postgresql+psycopg://sport:REMPLACER_PAR_LE_MOT_DE_PASSE@sport-db:5432/sport
COACH_API_KEY=REMPLACER_PAR_LA_CLE_COACH
```

Utiliser une valeur hexadécimale évite les problèmes d'encodage de caractères spéciaux dans `DATABASE_URL`.

Vérifier que `.env` est ignoré :

```bash
git check-ignore -v .env
```

## 7. Construire et démarrer la pile

```bash
cd /opt/sport
docker compose config --services
docker compose up -d --build
docker compose ps
```

Services attendus :

```text
sport-db
sport-backend
```

Consulter les logs :

```bash
docker compose logs --tail=100 sport-db
docker compose logs --tail=100 sport-backend
```

## 8. Appliquer les migrations

```bash
cd /opt/sport
docker compose exec sport-backend alembic upgrade head
docker compose exec sport-backend alembic current
```

La dernière commande doit afficher une révision marquée `(head)`.

Vérifier les tables :

```bash
docker compose exec sport-db \
  psql -U sport -d sport -c '\dt'
```

Ne pas supprimer les anciennes migrations Alembic, même si leur nom mentionne Strava.

## 9. Vérifier FastAPI

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/health/db
```

Résultats attendus :

```json
{"status":"ok"}
```

```json
{"status":"ok","database":true}
```

## 10. Authentifier Garmin Connect

### 10.1 Principe

La première connexion nécessite l'adresse e-mail et le mot de passe Garmin. Elle écrit ensuite un fichier de session dans :

```text
/opt/sport/garmin-tokens/garmin_tokens.json
```

Les synchronisations suivantes doivent réutiliser ce fichier. Refaire une connexion complète à chaque exécution peut provoquer une limitation HTTP 429.

### 10.2 État actuel du dépôt

L'authentification initiale a été réalisée pendant le développement avec `backend/app/garmin_test.py`. Ne supprimer ce fichier que lorsqu'un outil dédié, par exemple `app.services.garmin_auth`, aura été ajouté.

Si le script actuel demande l'e-mail et le mot de passe, lancer :

```bash
docker compose exec -it sport-backend python app/garmin_test.py
```

Ne jamais placer le mot de passe Garmin dans `.env`, Git, un script ou une commande conservée dans l'historique du shell.

Si le script actuel a déjà été remplacé par sa variante qui charge uniquement les jetons, deux solutions existent :

1. restaurer une copie sécurisée de `garmin_tokens.json` dans `garmin-tokens/` ;
2. ajouter au dépôt un utilitaire interactif dédié à la première authentification.

Une nouvelle installation n'est considérée comme reproductible que lorsque cette étape est documentée et testée avec le code présent dans le dépôt.

### 10.3 Vérifier les permissions

```bash
ls -la /opt/sport/garmin-tokens
chmod 700 /opt/sport/garmin-tokens
chmod 600 /opt/sport/garmin-tokens/garmin_tokens.json
```

Le fichier appartient parfois à `root` lorsqu'il est créé depuis le conteneur. C'est acceptable tant que le conteneur peut le lire et que les droits restent restrictifs.

## 11. Synchroniser Garmin

### 11.1 Synchronisation manuelle

```bash
cd /opt/sport
docker compose exec sport-backend \
  python -m app.services.garmin_sync
```

Une seconde exécution sans nouvelle activité ne doit pas créer de doublons.

### 11.2 Vérifier les activités

```bash
docker compose exec sport-db \
  psql -U sport -d sport \
  -c 'SELECT garmin_activity_id, name, start_date FROM activities ORDER BY start_date DESC LIMIT 10;'
```

Vérifier également les fichiers :

```bash
find /opt/sport/data/activities -maxdepth 2 -type f | tail -20
```

## 12. Automatiser la synchronisation

### 12.1 Préparer le script

```bash
chmod +x /opt/sport/scripts/sync-garmin.sh
```

Tester directement :

```bash
/opt/sport/scripts/sync-garmin.sh
```

### 12.2 Planification cron

Afficher la planification :

```bash
crontab -l
```

La ligne pour une exécution toutes les 15 minutes ressemble à :

```cron
*/15 * * * * /opt/sport/scripts/sync-garmin.sh
```

Modifier la fréquence :

```bash
crontab -e
```

Pour passer de 15 minutes à 5 minutes :

```cron
*/5 * * * * /opt/sport/scripts/sync-garmin.sh
```

Une fréquence plus élevée augmente les appels aux endpoints Garmin non officiels. Cinq à quinze minutes sont raisonnables pour un usage personnel, à condition de réutiliser les jetons persistés.

Si la crontab redirige les logs, conserver la redirection existante. Exemple :

```cron
*/15 * * * * /opt/sport/scripts/sync-garmin.sh >> /opt/sport/backups/garmin-sync.log 2>&1
```

Pour éviter que le journal grossisse sans limite, une migration future vers un service et un timer `systemd` est préférable.

### 12.3 Vérifier après redémarrage

```bash
sudo reboot
```

Après reconnexion :

```bash
docker compose -f /opt/sport/compose.yaml ps
crontab -l
curl -s http://localhost:8000/health/db
```

## 13. Générer le classeur Excel

```bash
cd /opt/sport
docker compose exec sport-backend \
  python -m app.services.generate_excel
```

Vérifier le fichier :

```bash
ls -lh /opt/sport/exports/sport.xlsx
file /opt/sport/exports/sport.xlsx
```

Le classeur est reconstruit depuis PostgreSQL. Il peut être supprimé puis régénéré.

Le coach voit les nouvelles activités via l'API immédiatement après la synchronisation. Excel ne les voit qu'après cette commande.

## 14. Utiliser l'API coach localement

Sans clé, l'accès doit être refusé :

```bash
curl -i 'http://localhost:8000/api/coach/context?days=42'
```

Avec la clé :

```bash
set -a
. /opt/sport/.env
set +a

curl -s \
  -H "Authorization: Bearer $COACH_API_KEY" \
  'http://localhost:8000/api/coach/context?days=42' \
  | python -m json.tool
```

Dernière activité trail :

```bash
curl -s \
  -H "Authorization: Bearer $COACH_API_KEY" \
  'http://localhost:8000/api/coach/activity/latest?sport_type=trail' \
  | python -m json.tool
```

Ne jamais copier la clé dans une capture, un ticket, un commit ou une conversation.

## 15. HTTPS et accès externe

### 15.1 Test temporaire

Un Quick Tunnel peut valider l'accès sans ouvrir de port sur la box :

```bash
docker run -d \
  --name sport-cloudflared-test \
  --network sport_default \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate \
  --protocol http2 \
  --url http://sport-backend:8000
```

Afficher l'adresse générée :

```bash
docker logs -f sport-cloudflared-test
```

Ce tunnel est temporaire. Son adresse change et il n'offre aucune garantie de disponibilité.

Arrêter puis supprimer le test :

```bash
docker stop sport-cloudflared-test
docker rm sport-cloudflared-test
```

### 15.2 Cible permanente

La cible est un tunnel Cloudflare nommé avec un domaine géré par Cloudflare. La documentation officielle est disponible ici :

- https://developers.cloudflare.com/tunnel/setup/
- https://developers.cloudflare.com/tunnel/

Le futur déploiement devra :

- ajouter un service `cloudflared` à `compose.yaml` ;
- placer le token du tunnel dans `.env` ou, de préférence, dans un fichier secret ;
- transmettre vers `http://sport-backend:8000` sur le réseau Docker ;
- utiliser `restart: unless-stopped` ;
- conserver PostgreSQL totalement inaccessible depuis Internet ;
- conserver l'authentification Bearer de FastAPI même derrière Cloudflare.

## 16. Sauvegarder et restaurer PostgreSQL

### 16.1 Créer une sauvegarde

```bash
cd /opt/sport
mkdir -p backups

docker compose exec -T sport-db \
  pg_dump -U sport -d sport -Fc \
  > "backups/sport-$(date +%F-%H%M).dump"
```

Vérifier :

```bash
ls -lh backups/
```

Copier ensuite le fichier vers un autre support ou une autre machine.

### 16.2 Tester une restauration

Une sauvegarde non testée ne constitue pas une garantie. Tester la restauration dans une base temporaire, jamais directement sur la base principale :

```bash
docker compose exec sport-db \
  createdb -U sport sport_restore_test
```

```bash
cat backups/NOM_DU_FICHIER.dump | \
docker compose exec -T sport-db \
  pg_restore -U sport -d sport_restore_test --clean --if-exists
```

Puis supprimer la base de test :

```bash
docker compose exec sport-db \
  dropdb -U sport sport_restore_test
```

## 17. Mettre le projet à jour

Avant une mise à jour :

```bash
cd /opt/sport
git status
docker compose exec -T sport-db \
  pg_dump -U sport -d sport -Fc \
  > "backups/pre-update-$(date +%F-%H%M).dump"
```

Puis :

```bash
git pull --ff-only
docker compose up -d --build
docker compose exec sport-backend alembic upgrade head
docker compose ps
curl -s http://localhost:8000/health/db
```

Générer ensuite Excel et lancer une synchronisation manuelle de contrôle.

## 18. Créer une migration après modification des modèles

```bash
cd /opt/sport
docker compose up -d --build
docker compose exec sport-backend \
  alembic revision --autogenerate -m "description de la modification"
```

Relire le fichier créé dans `backend/alembic/versions/`, puis :

```bash
docker compose exec sport-backend alembic upgrade head
docker compose exec sport-backend alembic current
```

Le montage `./backend/alembic:/app/alembic` permet de conserver sur l'hôte la migration créée dans le conteneur.

## 19. Diagnostic courant

### Backend indisponible

```bash
docker compose ps
docker compose logs --tail=200 sport-backend
curl -i http://localhost:8000/health
```

### Base indisponible

```bash
docker compose logs --tail=200 sport-db
docker compose exec sport-db pg_isready -U sport -d sport
curl -i http://localhost:8000/health/db
```

### Garmin HTTP 429

- ne pas relancer plusieurs connexions complètes ;
- vérifier que `garmin_tokens.json` est présent ;
- attendre avant un nouvel essai ;
- vérifier que le service utilise les jetons persistés.

### Excel absent

```bash
docker compose exec sport-backend \
  python -m app.services.generate_excel
docker compose logs --tail=100 sport-backend
ls -la exports/
```

### Cron ne s'exécute pas

```bash
crontab -l
ls -l scripts/sync-garmin.sh
/opt/sport/scripts/sync-garmin.sh
journalctl -u cron --since today
```

## 20. Préparer le premier commit

Avant `git add`, vérifier :

```bash
cd /opt/sport
git check-ignore -v \
  .env \
  garmin-tokens/garmin_tokens.json \
  exports/sport.xlsx
git add --dry-run .
```

Le dépôt ne doit contenir ni secrets, ni FIT, ni sauvegarde, ni classeur personnel.

Lorsque la liste est correcte :

```bash
git add .
git status
git commit -m "Initial sport platform"
```

## 21. Checklist après installation

- [ ] Docker et Compose fonctionnent sans `sudo`.
- [ ] `sport-db` est sain.
- [ ] `sport-backend` est démarré.
- [ ] Alembic est à `head`.
- [ ] `/health` et `/health/db` répondent.
- [ ] Les jetons Garmin existent avec des permissions restrictives.
- [ ] Une synchronisation manuelle réussit.
- [ ] Une seconde synchronisation ne crée pas de doublon.
- [ ] La tâche planifiée apparaît dans `crontab -l`.
- [ ] `sport.xlsx` est généré.
- [ ] L'API coach refuse les appels sans clé.
- [ ] Une sauvegarde PostgreSQL est créée et copiée hors de la Pi.

