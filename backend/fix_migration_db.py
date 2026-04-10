#!/usr/bin/env python
"""
Direct database fix for migration history inconsistency.

This script directly inserts the commerce.0001_initial migration record
into the database to fix the dependency issue.
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

def fix_migration_history_direct():
    """Directly fix migration history by inserting the record."""
    recorder = MigrationRecorder(connection)
    
    # Check if commerce.0001_initial is already recorded
    applied = recorder.applied_migrations()
    commerce_initial = ('commerce', '0001_initial')
    
    if commerce_initial in applied:
        print("✓ commerce.0001_initial is already in migration history.")
        return True
    
    # Insert the migration record using Django's recorder (handles all DB formats)
    print("Inserting commerce.0001_initial into migration history...")
    try:
        # Use Django's MigrationRecorder to record the migration
        # This handles all database-specific formatting automatically
        recorder.record_applied('commerce', '0001_initial')
        print("✓ Successfully inserted commerce.0001_initial into migration history")
        return True
    except Exception as e:
        print(f"✗ Error inserting migration record: {e}")
        print(f"  Database backend: {connection.vendor}")
        return False

if __name__ == '__main__':
    print("Fixing migration history directly in database...")
    if fix_migration_history_direct():
        print("\n✓ Migration history fixed!")
        print("You can now run: python3 manage.py migrate")
    else:
        print("\n✗ Failed to fix migration history.")
        print("\nAlternative: Try manually unapplying transactions.0002:")
        print("  python3 manage.py migrate transactions 0001_initial")
        sys.exit(1)
