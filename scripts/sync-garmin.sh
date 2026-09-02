#!/bin/bash

cd /opt/sport || exit 1

/usr/bin/docker compose exec -T sport-backend \
  python -m app.services.garmin_sync --limit 10
