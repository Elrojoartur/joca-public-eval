#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"
set -a
source .env.prod
set +a

cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py check
../.venv/bin/python manage.py runserver 0.0.0.0:8000
