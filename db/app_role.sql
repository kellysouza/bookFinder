-- Run once as the database owner. Do not commit a real password.
-- Cloud Run connects as bookfinder_app, not as the owner.
-- The role can read and insert. It cannot delete or change a saved nomination.

CREATE ROLE bookfinder_app LOGIN PASSWORD 'replace-me';
GRANT CONNECT ON DATABASE neondb TO bookfinder_app;
GRANT USAGE ON SCHEMA public TO bookfinder_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO bookfinder_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bookfinder_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT ON TABLES TO bookfinder_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO bookfinder_app;
