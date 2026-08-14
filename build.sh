#!/usr/bin/env bash
# Build step for platform deploys (Render, Railway, Fly, or a plain VPS).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
