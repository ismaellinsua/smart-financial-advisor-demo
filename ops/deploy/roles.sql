-- Database roles for NirKanA (PostgreSQL / Neon). Run once as the database owner, for example:
--   psql "$DATABASE_URL" -v app_role=neondb_owner -v backup_password="'una-contraseña-larga'" -f ops/deploy/roles.sql
-- (Neon: the owner role is the one in your connection string, usually neondb_owner.)
--
-- 1. The app's role keeps creating schemas and tables (it sets up each new business and migrates them at
--    start-up), but no statement or lock wait can hang for ever: a stuck transaction is cut off and its locks
--    released (refunds, voids and table charges lock rows while they run).
ALTER ROLE :app_role SET lock_timeout = '10s';
ALTER ROLE :app_role SET statement_timeout = '60s';
ALTER ROLE :app_role SET idle_in_transaction_session_timeout = '60s';

-- 2. A read-only role for the daily backups (BACKUP_DATABASES): it can read every business, change nothing.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nirkana_backup') THEN
    CREATE ROLE nirkana_backup LOGIN;
  END IF;
END
$$;
ALTER ROLE nirkana_backup PASSWORD :backup_password;
ALTER ROLE nirkana_backup SET default_transaction_read_only = on;
ALTER ROLE nirkana_backup SET statement_timeout = '15min';

-- Every schema there is now (the directory and each business)…
DO $$
DECLARE s record;
BEGIN
  FOR s IN SELECT nspname FROM pg_namespace
           WHERE nspname = 'public' OR nspname = 'nirkana_operador' OR nspname LIKE 'n\_%' LOOP
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO nirkana_backup', s.nspname);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO nirkana_backup', s.nspname);
    EXECUTE format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA %I TO nirkana_backup', s.nspname);
  END LOOP;
END
$$;
-- …and every schema and table the app creates from now on (new businesses).
ALTER DEFAULT PRIVILEGES FOR ROLE :app_role GRANT USAGE ON SCHEMAS TO nirkana_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE :app_role GRANT SELECT ON TABLES TO nirkana_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE :app_role GRANT SELECT ON SEQUENCES TO nirkana_backup;
