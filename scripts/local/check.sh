#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export COMPOSE_PROGRESS=plain
restore_local_services() {
  docker compose --profile test stop frontend-auth-test backend-auth-test worker-auth-test llm-test
  docker compose up -d --no-deps frontend worker
}
trap restore_local_services EXIT
# Keep a single E5 process and frontend active on memory-limited local machines.
docker compose stop worker
python3 scripts/local/test_bootstrap.py
python3 scripts/local/test_configure_llm.py

docker compose exec -T backend ruff check app migrations tests scripts
docker compose exec -T backend ruff format --check app migrations tests scripts
docker compose exec -T backend mypy
docker compose exec -T backend pytest -q -m "not integration"
# Stop test servers before the dedicated database schema is reset by integration tests.
docker compose --profile test stop frontend-auth-test backend-auth-test worker-auth-test llm-test
docker compose exec -T backend python scripts/test_database.py
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run typecheck
docker compose stop frontend
# Separate one-off service: production compilation cannot overwrite the live dev .next directory.
docker compose run --rm --no-deps -e NEXT_DIST_DIR=.next-build frontend npm run build
docker compose --profile test run --rm e2e
docker compose --profile test stop frontend-auth-test backend-auth-test worker-auth-test llm-test
python3 scripts/local/verify_conversation_persistence.py
