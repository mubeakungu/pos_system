#!/usr/bin/env sh

# Use Gunicorn to run the Flask application in production
# The --bind flag tells Gunicorn to listen on all public IPs, using the port
# provided by Render's environment variable.
gunicorn --bind 0.0.0.0:$PORT pos_system.app:app
