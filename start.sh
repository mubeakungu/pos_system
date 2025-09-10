#!/bin/bash

# Check for the existence of the 'migrations' directory.
# This is a one-time check to initialize the migration environment.
if [ ! -d "migrations" ]; then
    echo "--> Initializing Flask-Migrate..."
    # This command creates the 'migrations' directory and 'alembic.ini'.
    flask db init
fi

# Check if there are any migration scripts.
# This ensures a new initial script is created if one doesn't exist.
if [ -z "$(ls -A migrations/versions/)" ]; then
    echo "--> Creating initial migration script..."
    # This command generates a script based on your SQLAlchemy models.
    flask db migrate -m "Initial migration."
fi

# Always run db upgrade to apply any new changes to the database.
# This ensures your tables are up-to-date without deleting existing data.
echo "--> Running database upgrade..."
flask db upgrade

# Start the Gunicorn web server with your specified configuration.
echo "--> Starting Gunicorn server..."
gunicorn --bind 0.0.0.0:10000 --workers 4 --threads 2 app:app
