import sqlite3

import click
from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Youth Member'
        CHECK (role IN ('Youth Member', 'Leader')),
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0,
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
        db = get_db()
        db.executescript(SCHEMA)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
        if "is_admin" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        if "is_blocked" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
        db.execute("UPDATE users SET role = 'Youth Member' WHERE role IS NULL")
        admin_username = app.config["ADMIN_USERNAME"]
        admin_password = app.config["ADMIN_PASSWORD"]
        if admin_password:
            from werkzeug.security import generate_password_hash

            existing = db.execute(
                "SELECT id, is_admin FROM users WHERE username = ?",
                (admin_username,),
            ).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO users (username, password_hash, role, is_admin) "
                    "VALUES (?, ?, 'Youth Member', 1)",
                    (admin_username, generate_password_hash(admin_password)),
                )
            elif not existing["is_admin"]:
                db.execute(
                    "UPDATE users SET password_hash = ?, role = 'Youth Member', "
                    "is_admin = 1, is_blocked = 0 WHERE id = ?",
                    (generate_password_hash(admin_password), existing["id"]),
                )
        else:
            app.logger.warning(
                "ADMIN_PASSWORD is not set; the administrator account has not been created."
            )
        db.commit()
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
