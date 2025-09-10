# start.sh

# Set the FLASK_APP environment variable so Flask knows where to find the app
export FLASK_APP=app.py

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Run database migrations
flask db upgrade

# Start the Gunicorn server, binding to the port provided by Render
gunicorn --bind 0.0.0.0:$PORT app:app

