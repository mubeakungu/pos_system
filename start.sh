#!/bin/bash

Run database schema reset
echo "Resetting database schema..."
python db_reset.py

Start the web server
gunicorn --bind 0.0.0.0:10000 --workers 4 --threads 2 app:app
