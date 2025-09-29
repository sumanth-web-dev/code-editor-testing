#!/usr/bin/env python3
"""
Migration script to add missing phone and company_name fields to HR table
and create missing HR records for existing HR users.
"""

from app import app
from models import db, User, UserType, HR

def migrate_hr_fields():
    with app.app_context():
        try:
            # Add missing columns to HR table (if using SQLite, this might require manual intervention)
            print("Adding missing columns to HR table...")
            
            # Try to add columns (this might fail if they already exist)
            try:
                db.engine.execute('ALTER TABLE hr ADD COLUMN phone VARCHAR(20)')
                print("✓ Added phone column to HR table")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print("- Phone column already exists")
                else:
                    print(f"Error adding phone column: {e}")
            
            try:
                db.engine.execute('ALTER TABLE hr ADD COLUMN company_name VARCHAR(100)')
                print("✓ Added company_name column to HR table")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print("- Company_name column already exists")
                else:
                    print(f"Error adding company_name column: {e}")
            
            # Create missing HR records for existing HR users
            print("\nChecking for missing HR records...")
            hr_users = User.query.filter_by(user_type=UserType.HR).all()
            
            for user in hr_users:
                existing_hr = HR.query.filter_by(email=user.email).first()
                if not existing_hr:
                    print(f"Creating missing HR record for {user.email}")
                    hr = HR(email=user.email, user_id=user.id)
                    db.session.add(hr)
                else:
                    print(f"✓ HR record exists for {user.email}")
            
            db.session.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()

if __name__ == '__main__':
    migrate_hr_fields()