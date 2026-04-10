#!/usr/bin/env python3
"""
Script to create a Django superuser for admin panel access.
Run this script to create or update a superuser account.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def create_superuser():
    """Create or update a superuser account."""
    print("=" * 60)
    print("Django Admin Superuser Creation")
    print("=" * 60)
    
    # Get credentials
    username = input("Enter username (default: admin): ").strip() or "admin"
    email = input("Enter email (default: admin@example.com): ").strip() or "admin@example.com"
    password = input("Enter password (min 8 characters): ").strip()
    
    if len(password) < 8:
        print("❌ Error: Password must be at least 8 characters long.")
        return
    
    # Check if user exists
    try:
        user = User.objects.get(username=username)
        print(f"\n⚠️  User '{username}' already exists.")
        update = input("Do you want to make this user a superuser? (y/n): ").strip().lower()
        
        if update == 'y':
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.email = email
            user.set_password(password)
            user.save()
            print(f"✅ User '{username}' has been updated to superuser.")
        else:
            print("❌ Operation cancelled.")
            return
    except User.DoesNotExist:
        # Create new superuser
        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            print(f"✅ Superuser '{username}' created successfully!")
        except Exception as e:
            print(f"❌ Error creating superuser: {e}")
            return
    
    print("\n" + "=" * 60)
    print("Superuser Details:")
    print(f"  Username: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  Is Superuser: {user.is_superuser}")
    print(f"  Is Staff: {user.is_staff}")
    print(f"  Is Active: {user.is_active}")
    print("=" * 60)
    print("\n✅ You can now login to the admin panel at: /admin/")
    print(f"   Username: {user.username}")
    print(f"   Password: [the password you entered]")

if __name__ == "__main__":
    create_superuser()
