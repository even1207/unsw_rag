-- Basic Postgres schema for staff and publication tables.
CREATE TABLE IF NOT EXISTS staff (
    staff_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT,
    email TEXT,
    profile_url TEXT
);

CREATE TABLE IF NOT EXISTS publications (
    id SERIAL PRIMARY KEY,
    staff_id TEXT REFERENCES staff(staff_id),
    title TEXT NOT NULL,
    venue TEXT,
    year INT
);
