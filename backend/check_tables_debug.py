import sqlite3
import os

# Try various common paths
db_candidates = ['db.sqlite3', 'backend/db.sqlite3', '../db.sqlite3']
db_path = None
for candidate in db_candidates:
    if os.path.exists(candidate):
        db_path = candidate
        break

def list_relevant_tables():
    if not db_path:
        print("Database not found in common locations.")
        return
    
    print(f"Connected to: {os.path.abspath(db_path)}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    conn.close()
    
    print("\nFiltered tables for debugging:")
    keywords = ['escrow', 'transactions', 'properties', 'commerce', 'listing']
    for t in sorted(tables):
        if any(kw in t.lower() for kw in keywords):
            print(f" - {t}")
    
    print("\nDjango Migration history for check:")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT app, name FROM django_migrations;")
        migrations = cursor.fetchall()
        for app, name in migrations:
            if any(kw in app.lower() for kw in keywords):
                print(f" - {app}.{name}")
        conn.close()
    except Exception as e:
        print(f"Migration history check fails (possibly table missing): {e}")

if __name__ == "__main__":
    list_relevant_tables()
