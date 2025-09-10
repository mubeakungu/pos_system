# This script is a one-time tool to reset the database schema.
# It should only be run if you need to wipe all data and start fresh
# with a new set of SQLAlchemy models.

from app import app, db

with app.app_context():
    print("Dropping all existing tables...")
    db.drop_all()
    print("Creating new tables based on models...")
    db.create_all()
    print("Database schema reset complete.")

    # Re-create the admin user if it's the first run
    from app import User
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='pass123')
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created.")
