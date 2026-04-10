# Alternative Migration Fix Methods

## Method 1: Direct Database Fix (Recommended)

Run the direct database fix script:

```bash
cd backend
python3 fix_migration_db.py
```

This directly inserts the `commerce.0001_initial` record into the `django_migrations` table, bypassing Django's migration checks.

## Method 2: Unapply and Reapply

If Method 1 doesn't work, you can unapply the problematic migration and reapply in order:

```bash
cd backend

# Step 1: Unapply transactions.0002
python3 manage.py migrate transactions 0001_initial

# Step 2: Apply commerce.0001_initial
python3 manage.py migrate commerce 0001_initial

# Step 3: Reapply transactions.0002
python3 manage.py migrate transactions 0002_remove_order_buyer_remove_order_content_type_and_more

# Step 4: Continue with normal migrations
python3 manage.py migrate
```

## Method 3: Manual SQL Fix

If both methods fail, you can manually fix the database:

1. **Connect to your database** (SQLite, PostgreSQL, etc.)

2. **For SQLite:**
   ```sql
   INSERT INTO django_migrations (app, name, applied)
   VALUES ('commerce', '0001_initial', datetime('now'));
   ```

3. **For PostgreSQL:**
   ```sql
   INSERT INTO django_migrations (app, name, applied)
   VALUES ('commerce', '0001_initial', NOW());
   ```

4. **Then verify:**
   ```bash
   python3 manage.py showmigrations commerce
   ```

5. **Run migrations:**
   ```bash
   python3 manage.py migrate
   ```

## Method 4: Reset Migration History (Last Resort)

⚠️ **WARNING: This will lose migration history. Only use if you can recreate it.**

```bash
# Backup your database first!
# Then:
python3 manage.py migrate --fake-initial
```

## Why This Happened

- `transactions.0002` was applied to the database
- It depends on `commerce.0001_initial`
- `commerce.0001_initial` wasn't in the migration history yet
- Django detected this inconsistency and blocks all migration commands

## Prevention

Always apply migrations in dependency order:
1. Create all migrations first: `python3 manage.py makemigrations`
2. Review dependencies
3. Apply in order: `python3 manage.py migrate`
