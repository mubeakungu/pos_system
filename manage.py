# manage.py

import os
import sys
from flask.cli import FlaskGroup
from app import app, db, User, Product, Sale

def create_app():
    return app

cli = FlaskGroup(create_app=create_app)

@cli.command('create_admin')
def create_admin():
    """Creates a default admin user."""
    with app.app_context():
        # Check if the admin user already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if not existing_admin:
            admin_user = User(username='admin', password='pass123')
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Default admin user created.")
        else:
            print("✅ Admin user already exists.")

if __name__ == '__main__':
    cli()
