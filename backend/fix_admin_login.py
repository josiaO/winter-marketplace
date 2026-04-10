#!/usr/bin/env python3
"""
Diagnostic script to check admin login issues.
Run this to verify superuser status and check for common issues.
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

print("=" * 60)
print("Admin Login Diagnostic")
print("=" * 60)

# Check all superusers
superusers = User.objects.filter(is_superuser=True)
print(f"\n📊 Found {superusers.count()} superuser(s):")
for user in superusers:
    print(f"\n  Username: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  Is Superuser: {user.is_superuser}")
    print(f"  Is Staff: {user.is_staff}")
    print(f"  Is Active: {user.is_active}")
    print(f"  Last Login: {user.last_login}")
    print(f"  Date Joined: {user.date_joined}")
    
    # Test password
    test_password = input(f"\n  Test password for {user.username}? (y/n): ").strip().lower()
    if test_password == 'y':
        password = input("  Enter password: ").strip()
        if user.check_password(password):
            print("  ✅ Password is correct!")
        else:
            print("  ❌ Password is incorrect!")
            reset = input("  Reset password? (y/n): ").strip().lower()
            if reset == 'y':
                new_password = input("  Enter new password: ").strip()
                if len(new_password) >= 8:
                    user.set_password(new_password)
                    user.save()
                    print("  ✅ Password reset successfully!")
                else:
                    print("  ❌ Password must be at least 8 characters.")

print("\n" + "=" * 60)
print("Settings Check:")
print("=" * 60)

from django.conf import settings
print(f"DEBUG: {settings.DEBUG}")
print(f"SESSION_COOKIE_SECURE: {settings.SESSION_COOKIE_SECURE}")
print(f"SESSION_COOKIE_SAMESITE: {getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Not set')}")
print(f"CSRF_COOKIE_SECURE: {settings.CSRF_COOKIE_SECURE}")

# Check for cookie issues
if settings.SESSION_COOKIE_SAMESITE == 'None' and not settings.SESSION_COOKIE_SECURE:
    print("\n⚠️  WARNING: SESSION_COOKIE_SAMESITE='None' requires SESSION_COOKIE_SECURE=True")
    print("   This can prevent cookies from being set in development!")
    print("   Fix: Set SESSION_COOKIE_SAMESITE='Lax' in development")

print("\n" + "=" * 60)
print("Recommendations:")
print("=" * 60)
print("1. Ensure user is_active=True, is_staff=True, is_superuser=True")
print("2. Check browser console for cookie/session errors")
print("3. Try incognito/private browsing mode")
print("4. Clear browser cookies for the admin site")
print("5. Check if CSRF token is being sent correctly")
print("=" * 60)
