import sqlite3

import click
from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT CHECK (role IN ('Youth Member', 'Leader') OR role IS NULL),
    bio TEXT NOT NULL DEFAULT '',
    birthday TEXT,
    profile_image TEXT,
    postal_code TEXT,
    area TEXT,
    latitude REAL,
    longitude REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    event_date TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS events_date_idx ON events(event_date);

CREATE TABLE IF NOT EXISTS gallery_days (
    gallery_date TEXT PRIMARY KEY,
    opened_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gallery_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gallery_date TEXT NOT NULL REFERENCES gallery_days(gallery_date) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS gallery_photos_date_idx
    ON gallery_photos(gallery_date, uploaded_at);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_db(app):
    with app.app_context():
        get_db().executescript(SCHEMA)
        get_db().commit()
    app.cli.add_command(init_db_command)


def close_db(_error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


@click.command("init-db")
def init_db_command():
    get_db().executescript(SCHEMA)
    get_db().commit()
    click.echo("Database is ready.")
