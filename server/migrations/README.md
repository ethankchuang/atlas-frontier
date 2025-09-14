# Database Migrations

This directory contains SQL migration files for database schema changes.

## Naming Convention

Migration files should be named with the format:
```
{number}_{description}.sql
```

Examples:
- `001_multiple_players_per_user.sql`
- `002_add_inventory_system.sql`
- `003_update_user_permissions.sql`

## How to Run Migrations

1. **Manual Approach (Current)**:
   - Copy the SQL content from the migration file
   - Paste it into your Supabase SQL Editor
   - Execute the migration

2. **Future Automated Approach**:
   - We could add a migration runner script that:
     - Tracks which migrations have been applied
     - Runs pending migrations in order
     - Provides rollback capabilities

## Migration Files

- `001_multiple_players_per_user.sql` - Adds support for multiple players per user profile

## Best Practices

1. **Always backup your database before running migrations**
2. **Test migrations on staging environment first**
3. **Make migrations reversible when possible**
4. **Keep migrations small and focused**
5. **Document breaking changes**

## Migration Tracking

Currently, we don't have automated migration tracking. Consider adding a `migrations` table to track applied migrations:

```sql
CREATE TABLE migrations (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```
