import sqlite3
import os

# Database Path (adjust if necessary)
db_path = 'db.sqlite3'
if not os.path.exists(db_path):
    print(f"Warning: {db_path} not found in root, trying current directory.")

def clean_escrow_tables():
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found. Please run from the directory containing db.sqlite3.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    # Identify tables to drop (escrow_engine and legacy transactions)
    to_drop = [t for t in tables if t.startswith('escrow_engine_') or t.startswith('transactions_')]
    
    if not to_drop:
        print("No escrow or transaction tables found to clean up.")
        return
    
    print(f"Found {len(to_drop)} tables to clean up.")
    
    # Drop them
    for table in to_drop:
        print(f" - Dropping table: {table}")
        cursor.execute(f"DROP TABLE IF EXISTS \"{table}\"")
    
    # Also clear the migration record if it exists
    print("Cleaning up stale migration records for 'escrow_engine'...")
    cursor.execute("DELETE FROM django_migrations WHERE app = 'escrow_engine'")
    
    conn.commit()
    conn.close()
    print("\nCleanup complete! You can now run: python3 manage.py migrate --fake-initial")

if __name__ == "__main__":
    clean_escrow_tables()
