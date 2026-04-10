import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection

def cleanup_migration_history():
    # List of apps being reset/consolidated
    apps_to_clear = [
        'accounts', 'analytics', 'catalog', 'commerce', 'communications',
        'core', 'escrow_engine', 'insights', 'marketplace', 'trust', 
        'wallets', 'media_app', 'listings', 'features', 'shortlinks',
        'search', 'properties'
    ]
    
    print(f"Cleaning up migration history for: {', '.join(apps_to_clear)}")
    
    with connection.cursor() as cursor:
        # Delete entries from django_migrations for these apps
        # This allows --fake-initial to record the new initial migrations correctly
        placeholders = ', '.join(['%s'] * len(apps_to_clear))
        query = f"DELETE FROM django_migrations WHERE app IN ({placeholders})"
        cursor.execute(query, apps_to_clear)
        print(f"Removed {cursor.rowcount} entries from django_migrations.")

if __name__ == "__main__":
    try:
        cleanup_migration_history()
        print("\nSuccess! Now you can run:")
        print("python3 manage.py migrate --fake-initial")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
