#!/usr/bin/env bash

set -u

PROJECT_DIR="/opt/sport"
PUBLIC_URL="${SPORT_PUBLIC_URL:-https://rpi-home.tail3f4428.ts.net}"

cd "$PROJECT_DIR" || exit 1

if [ -f "$PROJECT_DIR/.env" ]; then
    configured_public_url=$(sed -n 's/^SPORT_PUBLIC_URL=//p' "$PROJECT_DIR/.env" | tail -n 1)

    if [ -n "$configured_public_url" ]; then
        PUBLIC_URL="$configured_public_url"
    fi
fi

log() {
    printf '[sport-watchdog] %s\n' "$*"
}

if ! docker compose ps --status running -q sport-backend | grep -q .; then
    log "sport-backend is not running; starting the Compose stack"
    docker compose up -d
fi

if ! curl -fsS --max-time 8 http://127.0.0.1:8000/health >/dev/null; then
    log "local FastAPI healthcheck failed; restarting sport-backend"
    docker compose restart sport-backend
fi

if ! systemctl is-active --quiet tailscaled; then
    log "tailscaled is not active; restarting it"
    systemctl restart tailscaled
fi

if ! tailscale status >/dev/null 2>&1; then
    log "Tailscale is not connected; attempting to restart tailscaled"
    systemctl restart tailscaled
fi

if ! tailscale funnel status 2>/dev/null | grep -q "Funnel on"; then
    log "Funnel is not enabled; reapplying the FastAPI proxy"
    tailscale funnel --bg http://127.0.0.1:8000
fi

# This check catches a stale public edge when the Pi can still serve locally.
if ! curl -fsS --max-time 12 "$PUBLIC_URL/health" >/dev/null; then
    log "public healthcheck failed; refreshing the Funnel proxy"
    tailscale funnel --https=443 off || true
    tailscale funnel --bg http://127.0.0.1:8000
fi
