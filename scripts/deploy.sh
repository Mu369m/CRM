#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

cd "$ROOT_DIR"

echo "==> Updating source"
git pull --ff-only origin "$(git branch --show-current)"

echo "==> Validating production configuration"
"${COMPOSE[@]}" config --quiet

echo "==> Applying database migrations"
"${COMPOSE[@]}" run --rm --no-deps --entrypoint alembic api upgrade head

echo "==> Building production images"
"${COMPOSE[@]}" build --pull api web worker

echo "==> Rolling application services"
"${COMPOSE[@]}" up -d --no-deps --remove-orphans api web worker

echo "==> Waiting for API health"
for attempt in $(seq 1 30); do
    if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" >/dev/null 2>&1; then
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "API did not become healthy" >&2
        "${COMPOSE[@]}" logs --tail=100 api
        exit 1
    fi
    sleep 2
done

echo "==> Reloading reverse proxy"
"${COMPOSE[@]}" up -d nginx
"${COMPOSE[@]}" exec -T nginx nginx -t
"${COMPOSE[@]}" exec -T nginx nginx -s reload

echo "Deployment completed successfully"