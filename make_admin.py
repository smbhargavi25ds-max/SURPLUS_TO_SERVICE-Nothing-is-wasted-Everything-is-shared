"""
Run this once to make yourself admin:
  python make_admin.py your@email.com
"""
import sys
import os
from app import app, db, User

if len(sys.argv) < 2:
    print("Usage: python make_admin.py your@email.com")
    sys.exit(1)

email = sys.argv[1]

with app.app_context():
    user = User.query.filter_by(email=email).first()
    if not user:
        print(f"No user found with email: {email}")
        sys.exit(1)
    user.is_admin = True
    db.session.commit()
    print(f"✓ {user.username} ({email}) is now an admin.")
