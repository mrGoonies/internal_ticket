#!/usr/bin/env bash
# Build command para Render. Ver render.yaml.
set -o errexit

pip install uv
uv sync --frozen

uv run python manage.py collectstatic --noinput
uv run python manage.py migrate
