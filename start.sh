#!/usr/bin/env sh
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:$PORT app:app
