# CoachGoggins

Coach sportif personnel alimente par Garmin Connect. Les activites sont
synchronisees sur une Raspberry Pi, stockees dans PostgreSQL, resumees dans un
classeur Excel et exposees a un coach IA par une API HTTPS protegee.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) : composants, donnees et fonctionnement.
- [Installation](docs/INSTALLATION.md) : installation complete et commandes de maintenance.
- [Guide du coach IA](docs/COACH_IA.md) : endpoints, methode d'analyse et limites.
- [Action OpenAPI](docs/coach-action.openapi.yaml) : contrat en lecture seule pour un GPT prive.
- [Instructions du GPT](docs/COACH_GPT_INSTRUCTIONS.md) : texte a placer dans le configurateur du coach.

## Confidentialite

Ne jamais versionner `.env`, les tokens Garmin, les fichiers FIT, les sauvegardes
PostgreSQL, ni les exports personnels. La cle `COACH_API_KEY` doit etre saisie
dans le gestionnaire de secrets de l'action GPT, jamais dans un document ou un
commit.
