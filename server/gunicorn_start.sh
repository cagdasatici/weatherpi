#!/usr/bin/env bash
# Simple launcher for Gunicorn to run the Flask proxy in production
# Make executable: chmod +x server/gunicorn_start.sh

APP_MODULE=server.app:app
WORKERS=${GUNICORN_WORKERS:-3}
BIND=${GUNICORN_BIND:-0.0.0.0:8000}

exec gunicorn --workers ${WORKERS} --bind ${BIND} --access-logfile - --error-logfile - ${APP_MODULE}
