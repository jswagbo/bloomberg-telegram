-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
