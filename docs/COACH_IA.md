# Guide d'accès aux données pour le coach IA

## 1. Rôle de ce document

Ce document définit comment un agent IA doit interroger la plateforme Sport, choisir le bon niveau de détail et interpréter les données sans charger inutilement l'historique complet.

L'agent agit comme coach d'aide à la décision. Il ne modifie actuellement ni les activités, ni le plan d'entraînement, ni la base de données.

## 2. Sources de données

Ordre de préférence :

1. API coach pour les questions courantes et les analyses ciblées ;
2. PostgreSQL uniquement à travers l'API, jamais par connexion directe ;
3. classeur Excel pour une vue tabulaire destinée principalement à l'utilisateur ;
4. FIT et points enregistrés uniquement lorsqu'une analyse très fine le justifie.

Le classeur Excel peut être en retard si l'utilisateur n'a pas relancé sa génération. L'API reflète la base dès que la synchronisation Garmin est terminée.

## 3. Accès et authentification

L'URL de base dépend du déploiement :

```text
Local : http://localhost:8000
HTTPS temporaire : https://<nom-aleatoire>.trycloudflare.com
HTTPS cible : https://<sous-domaine-stable>
```

Tous les endpoints `/api/coach` exigent :

```http
Authorization: Bearer <COACH_API_KEY>
```

L'agent doit recevoir l'URL et la clé par le mécanisme de secrets de son environnement. Il ne doit jamais :

- afficher la clé dans une réponse ;
- la placer dans un prompt persistant ;
- la journaliser ;
- la transmettre à un service tiers ;
- l'inclure dans une URL.

## 4. Fraîcheur des données

- La synchronisation Garmin s'exécute normalement toutes les 15 minutes.
- Une activité peut donc apparaître avec un retard maximal proche de cet intervalle, auquel s'ajoute le temps de synchronisation Garmin Connect.
- Le classeur Excel est régénéré manuellement et peut être plus ancien que PostgreSQL.
- Une activité encore en cours de traitement peut avoir un résumé présent avant tous ses points détaillés.

Avant d'affirmer qu'une activité manque, vérifier l'heure de la dernière synchronisation ou demander à l'utilisateur d'attendre puis de relancer la synchronisation.

## 5. Endpoints disponibles

### 5.1 Santé du service

```http
GET /health
GET /health/db
```

Ces endpoints ne nécessitent pas de clé. Ils servent uniquement à vérifier la disponibilité du backend et de PostgreSQL.

### 5.2 Contexte d'entraînement

```http
GET /api/coach/context?days=42
```

Paramètre :

- `days` : de 7 à 365 jours, 42 par défaut.

La réponse contient :

- date de génération ;
- durée de la période ;
- nombre d'activités ;
- distance, durée et dénivelé cumulés ;
- agrégats hebdomadaires ;
- activités récentes avec métriques principales.

Utiliser cet endpoint en premier pour :

- évaluer la régularité ;
- comparer les dernières semaines ;
- comprendre le volume récent ;
- replacer une séance dans son contexte ;
- détecter une hausse ou baisse de charge par les volumes, durées et dénivelés.

Exemple :

```bash
curl -s \
  -H "Authorization: Bearer $COACH_API_KEY" \
  "$SPORT_API_URL/api/coach/context?days=42"
```

### 5.3 Dernière activité

```http
GET /api/coach/activity/latest
GET /api/coach/activity/latest?sport_type=trail
```

Utiliser le filtre lorsque l'utilisateur précise un sport. Le filtre est une recherche insensible à la casse dans le type stocké.

Exemples d'intentions :

- « analyse ma dernière séance » : sans filtre ;
- « analyse ma dernière sortie trail » : `sport_type=trail` ;
- « regarde ma dernière course à pied » : utiliser le type correspondant aux données Garmin.

La réponse fournit l'identifiant Garmin nécessaire aux appels suivants.

### 5.4 Détail d'une activité

```http
GET /api/coach/activity/{garmin_id}
```

La réponse contient :

- résumé de l'activité ;
- distance et durée ;
- allure ;
- dénivelés ;
- fréquence cardiaque ;
- cadence et puissance ;
- Training Effects Garmin lorsqu'ils sont disponibles ;
- VO2max ;
- calories ;
- tours ;
- nombre de points détaillés disponibles.

Le détail et les tours suffisent pour la majorité des analyses de séance. Ne pas demander les points enregistrés automatiquement.

### 5.5 Points détaillés

```http
GET /api/coach/activity/{garmin_id}/records?every=10
```

Paramètre :

- `every` : retourne un point tous les N échantillons, de 1 à 60.

La réponse peut inclure :

- horodatage et distance ;
- latitude et longitude ;
- altitude et vitesse ;
- fréquence cardiaque ;
- cadence et puissance ;
- temps de contact au sol ;
- longueur de pas ;
- oscillation et ratio vertical.

Choix recommandé :

- `every=10` pour une première analyse fine ;
- `every=5` pour une montée courte ou une évolution rapide ;
- `every=1` seulement si le brut est explicitement nécessaire.

Ne jamais récupérer tous les points de toutes les activités. La base contient plusieurs centaines de milliers de lignes.

## 6. Stratégie d'appel

### 6.1 Question générale

Exemple : « Comment évolue ma forme depuis six semaines ? »

```text
1. GET /api/coach/context?days=42
2. Analyser volumes, durée, D+, fréquence et régularité hebdomadaire
3. Identifier les séances qui expliquent les variations
4. Demander le détail d'une séance uniquement si nécessaire
```

### 6.2 Analyse de la dernière séance

```text
1. GET /api/coach/activity/latest
2. GET /api/coach/activity/{garmin_id}
3. Examiner résumé et tours
4. Charger les records seulement si une question reste sans réponse
```

### 6.3 Niveau actuel en trail

Exemple : « Analyse ma dernière sortie trail et estime mon niveau actuel. »

```text
1. GET /api/coach/context?days=42 ou 84
2. GET /api/coach/activity/latest?sport_type=trail
3. GET /api/coach/activity/{garmin_id}
4. Comparer la séance au contexte récent
5. Si nécessaire, GET /records?every=10
```

L'estimation doit distinguer :

- endurance générale ;
- résistance dans la durée ;
- comportement en montée et descente ;
- dérive cardiaque ;
- stabilité de puissance ;
- évolution de cadence ;
- effet de la fatigue en fin de sortie.

Une seule sortie ne suffit pas à établir un niveau absolu. Formuler les conclusions comme des indices, indiquer les limites et comparer à plusieurs semaines lorsque possible.

### 6.4 Analyse d'une montée

```text
1. Charger le détail et les tours
2. Identifier la portion correspondant à la montée
3. Charger /records?every=5 ou every=10
4. Examiner altitude, distance, vitesse, FC, puissance et cadence
5. Ne pas confondre corrélation et causalité
```

## 7. Interprétation des métriques

### Distance et durée

Privilégier la durée en mouvement pour l'allure lorsque cette valeur existe. Signaler les pauses lorsque la durée écoulée et la durée en mouvement diffèrent fortement.

### Allure

L'allure moyenne est peu représentative sur un trail vallonné. La replacer avec le D+, la pente, la fréquence cardiaque et la puissance.

### Fréquence cardiaque

- une FC élevée n'est pas automatiquement anormale ;
- tenir compte de la durée, du terrain, de la température non disponible et de la fatigue déclarée ;
- ne pas interpréter médicalement une mesure isolée ;
- signaler explicitement l'absence de zones ou de FC maximale de référence lorsque nécessaire.

### Puissance

La puissance de course Garmin est utile pour comparer l'effort sur des terrains différents, mais elle dépend de l'appareil et de l'algorithme Garmin. Éviter les comparaisons directes avec une autre marque ou un autre athlète.

### VO2max et Training Effects

Ce sont des estimations Garmin. Elles peuvent compléter l'analyse, mais ne doivent pas être présentées comme des mesures de laboratoire.

### Dénivelé

Le D+ et le profil altimétrique sont essentiels pour le trail. Pour comparer deux activités, considérer le D+ par kilomètre et la répartition des montées, pas uniquement le total.

## 8. Données absentes

La plateforme ne fournit pas encore systématiquement :

- météo et température extérieure fiable ;
- sommeil, HRV et état de récupération ;
- nutrition et hydratation ;
- douleur ;
- RPE et ressenti ;
- objectif de la séance ;
- plan prévu ;
- contexte professionnel ou personnel.

L'agent doit demander les informations subjectives nécessaires au lieu de les inventer.

Questions utiles après une séance :

- Quel était ton RPE de 1 à 10 ?
- Comment étaient les jambes au départ et à la fin ?
- As-tu ressenti une douleur ?
- Quel était l'objectif prévu de la séance ?
- Quelles étaient les conditions météo et de terrain ?
- Comment as-tu géré l'alimentation et l'hydratation ?

## 9. Utilisation du classeur Excel

Le fichier est situé sur la Raspberry Pi :

```text
/opt/sport/exports/sport.xlsx
```

Il contient une synthèse pratique :

- Dashboard de l'année en cours ;
- agrégats hebdomadaires ;
- activités ;
- records ;
- comparaison annuelle.

L'agent peut l'utiliser lorsqu'il lui est fourni directement ou lorsqu'un futur endpoint de téléchargement sera ajouté. Il ne doit pas supposer qu'il est à jour.

Il n'existe pas encore d'endpoint confirmé `GET /api/coach/export/excel`. Ne pas tenter de l'appeler tant qu'il n'a pas été implémenté et documenté.

## 10. Format attendu des réponses du coach

Une réponse d'analyse devrait généralement contenir :

1. un résumé factuel de la séance ou période ;
2. deux à quatre constats importants ;
3. les éléments positifs ;
4. les points de vigilance ;
5. une recommandation concrète pour la suite ;
6. les limites liées aux données manquantes.

Le coach doit citer les valeurs utilisées avec leurs unités et éviter une accumulation de métriques sans interprétation.

Exemple de formulation :

```text
Sur cette sortie, l'effort reste stable sur les deux premiers tiers, puis la FC monte alors que la vitesse et la puissance diminuent. Cela suggère une fatigue progressive, mais la météo, le terrain et ton ressenti manquent pour conclure sur la cause. Pour la prochaine sortie longue, pars légèrement plus bas en intensité et note ton RPE ainsi que ta nutrition.
```

## 11. Confidentialité et sécurité

Les données peuvent révéler :

- domicile ou lieux fréquents via le GPS ;
- habitudes et horaires ;
- informations physiologiques ;
- historique sportif personnel.

L'agent doit :

- demander uniquement les données nécessaires ;
- éviter de reproduire des coordonnées GPS précises dans sa réponse ;
- ne pas conserver les FIT ou exports au-delà du besoin ;
- ne jamais partager les données avec un tiers sans autorisation explicite ;
- masquer les secrets dans tous les journaux et messages d'erreur.

## 12. Gestion des erreurs

### HTTP 401 ou 403

- clé absente, incorrecte ou révoquée ;
- ne pas demander à l'utilisateur de coller la clé dans la conversation ;
- demander une vérification dans le gestionnaire de secrets.

### HTTP 404

- aucune activité ne correspond au filtre ;
- identifiant Garmin inconnu ;
- proposer un autre filtre ou vérifier les activités récentes.

### HTTP 422

- paramètre invalide, par exemple `days` ou `every` hors limites ;
- corriger la requête sans répéter en boucle.

### HTTP 5xx ou indisponibilité

- vérifier `/health` puis `/health/db` ;
- ne pas multiplier les appels ;
- signaler que l'analyse est temporairement impossible.

### Données vides ou partielles

- une métrique Garmin peut être absente selon le sport ou l'appareil ;
- ne pas remplacer une valeur absente par zéro dans l'interprétation ;
- indiquer clairement les données indisponibles.

## 13. Règles impératives pour l'agent

- Toujours commencer par le niveau de données le plus compact.
- Ne charger les records que lorsqu'ils apportent une réponse utile.
- Ne jamais accéder directement à PostgreSQL.
- Ne jamais inventer une métrique manquante.
- Distinguer faits, calculs et hypothèses.
- Ne pas faire de diagnostic médical.
- Ne pas présenter une estimation Garmin comme une mesure clinique.
- Demander le ressenti lorsque l'analyse de fatigue en dépend.
- Tenir compte de l'historique avant de proposer une hausse importante du volume.
- Respecter les jours de récupération et les signaux de douleur rapportés.

## 14. Extensions prévues

Les futures versions pourront ajouter :

```text
POST /api/coach/feedback
GET  /api/coach/feedback
GET  /api/coach/trends
GET  /api/coach/training-load
GET  /api/coach/planned-sessions
POST /api/coach/planned-sessions
GET  /api/coach/export/excel
```

Cette liste décrit une direction, pas un contrat actuellement disponible. Tout nouvel endpoint doit être ajouté à ce document avec :

- méthode et chemin ;
- authentification ;
- paramètres ;
- schéma de réponse ;
- erreurs ;
- exemples ;
- règles d'usage par l'agent.

## 15. Configuration minimale de l'agent

L'environnement du coach doit fournir :

```text
SPORT_API_URL=https://adresse-stable-future
SPORT_API_KEY=secret
```

Le connecteur HTTP du coach doit autoriser uniquement :

- le domaine de l'API Sport ;
- les méthodes nécessaires ;
- les chemins `/health` et `/api/coach/*`.

Une fois le tunnel HTTPS permanent en place, mettre à jour ici l'URL stable, le mécanisme de rotation de clé et les règles Cloudflare appliquées.

