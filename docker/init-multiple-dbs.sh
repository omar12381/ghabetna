#!/bin/bash
# Crée les bases de données supplémentaires au démarrage de PostgreSQL
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE incident_db;
    GRANT ALL PRIVILEGES ON DATABASE incident_db TO $POSTGRES_USER;
EOSQL
