#!/bin/bash

Ensure the migrations folder exists before running any migrations
if [ ! -d "migrations" ]; then
echo "Migrations directory not found, initializing..."
flask db init
flask db migrate -m "Initial migration"
fi

Run database migrations
flask db upgrade

Start the web server
gunicorn --bind 0.0.0.0:10000 --workers 4 --threads 2 app:app
