#!/usr/bin/env sh

Install dependencies from requirements.txt
pip install -r requirements.txt

Start the Gunicorn server. The --bind flag tells Gunicorn to listen on
all public IPs, using the port provided by Render's environment variable.
gunicorn --bind 0.0.0.0:$PORT app:app
