#!/usr/bin/env python
"""
Script to fix migration history inconsistency.

This script fake-applies commerce.0001_initial to fix the dependency issue
where transactions.0002 was applied before commerce.0001_initial.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
from django.db.migrations.recorder import MigrationRecorder

def fix_migration_history():
    """Fix the migration history by fake-applying commerce.0001_initial."""
    recorder = MigrationRecorder(connection)
    
    # Check if commerce.0001_initial is already recorded
    applied = recorder.applied_migrations()
    commerce_initial = ('commerce', '0001_initial')
    
    if commerce_initial in applied:
        print(f"✓ {commerce_initial[0]}.{commerce_initial[1]} is already applied.")
        return True
    
    # Fake-apply the migration
    print(f"Fake-applying {commerce_initial[0]}.{commerce_initial[1]}...")
    try:
        call_command('migrate', 'commerce', '0001_initial', '--fake', verbosity=1)
        print(f"✓ Successfully fake-applied {commerce_initial[0]}.{commerce_initial[1]}")
        return True
    except Exception as e:
        print(f"✗ Error fake-applying migration: {e}")
        return False

if __name__ == '__main__':
    print("Fixing migration history...")
    if fix_migration_history():
        print("\n✓ Migration history fixed!")
        print("You can now run: python3 manage.py migrate")
    else:
        print("\n✗ Failed to fix migration history.")
        sys.exit(1)
