# Fix Migration History Issue

## Problem
The migration `transactions.0002` was applied to the database before its dependency `commerce.0001_initial` was applied, creating an inconsistent migration history.

## Solution

### Option 1: Use the Fix Script (Recommended)

Run the automated fix script:

```bash
cd backend
python3 fix_migration_history.py
```

Then run normal migrations:

```bash
python3 manage.py migrate
```

### Option 2: Manual Fix

You need to fake-apply the commerce.0001_initial migration to fix the history:

```bash
cd backend
python3 manage.py migrate commerce 0001_initial --fake
```

This will mark `commerce.0001_initial` as applied in the migration history without actually running it (since the dependency issue needs to be resolved first).

After that, you can run normal migrations:

```bash
python3 manage.py migrate
```

## Alternative Solution (if fake doesn't work)

If the fake approach doesn't work, you can manually fix the migration history:

1. **Check current migration state:**
   ```bash
   python3 manage.py showmigrations commerce
   python3 manage.py showmigrations transactions
   ```

2. **If commerce.0001_initial shows as not applied, fake it:**
   ```bash
   python3 manage.py migrate commerce 0001_initial --fake
   ```

3. **Then run normal migrations:**
   ```bash
   python3 manage.py migrate
   ```

## Why This Happened

The `transactions.0002` migration was created with a dependency on `commerce.__first__`, which was later resolved to `commerce.0001_initial`. However, the migration was applied to the database before the commerce migrations were created/applied, causing the inconsistency.

## Prevention

In the future, always:
1. Create migrations for all apps that have dependencies
2. Apply migrations in dependency order
3. Use specific migration names in dependencies rather than `__first__` when possible
