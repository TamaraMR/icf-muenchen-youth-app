import base64
import io
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date

from youth_app import create_app
from youth_app.db import get_db


PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j8XcAAAAASUVORK5CYII="
)


class YouthAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
                "DATABASE": os.path.join(self.temp_dir.name, "test.sqlite"),
                "UPLOAD_FOLDER": os.path.join(self.temp_dir.name, "uploads"),
                "ADMIN_PASSWORD": "test-admin-password",
                "GALLERY_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def post(self, client, path, data=None, **kwargs):
        with client.session_transaction() as session:
            token = session.setdefault("_csrf_token", "test-csrf-token")
        return client.post(path, data={"csrf_token": token, **(data or {})}, **kwargs)

    def create_user(self, username, role="Youth Member"):
        client = self.app.test_client()
        self.post(client, "/register", {"username": username, "password": "test-password"})
        response = self.post(client, "/login", {"username": username, "password": "test-password"})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            get_db().execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
            get_db().commit()
        return client

    def test_registration_starts_as_member_and_profile(self):
        response = self.post(
            self.client,
            "/register",
            {"username": "sam_01", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.post(
                self.client,
                "/register",
                {"username": "SAM_01", "password": "different-password"},
            ).status_code,
            200,
        )
        self.post(self.client, "/login", {"username": "sam_01", "password": "test-password"})
        self.assertIn(b"Welcome to the ICF M", self.client.get("/").data)
        self.assertEqual(self.client.get("/choose-role").status_code, 404)
        self.assertEqual(self.client.get("/profile").status_code, 200)

        response = self.post(
            self.client,
            "/profile",
            {
                "bio": "Here for the good people.",
                "birthday": "2004-06-12",
                "profile_image": (io.BytesIO(PIXEL_PNG), "profile.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            person = get_db().execute(
                "SELECT bio, birthday, profile_image FROM users WHERE username = 'sam_01'"
            ).fetchone()
            self.assertEqual(
                (person["bio"], person["birthday"]),
                ("Here for the good people.", "2004-06-12"),
            )
            self.assertTrue(person["profile_image"].endswith(".png"))
            self.assertEqual(
                self.post(
                    self.client,
                    "/map",
                    {
                        "postal_code": "80331",
                        "area": "Altstadt",
                        "latitude": "48.1372",
                        "longitude": "11.5756",
                    },
                ).status_code,
                302,
            )
            map_page = self.client.get("/map").data
            self.assertIn(f"/uploads/{person['profile_image']}".encode(), map_page)
            image_response = self.client.get(f"/uploads/{person['profile_image']}")
        self.assertEqual(image_response.status_code, 200)
        image_response.close()
        calendar_page = self.client.get("/calendar?year=2026&month=6").data
        self.assertIn(b"birthday-item", calendar_page)
        self.assertIn(b"sam_01", calendar_page)

    def test_posts_require_csrf_token(self):
        response = self.client.post("/register", data={"username": "sam", "password": "test-password"})
        self.assertEqual(response.status_code, 400)

    def test_only_leaders_can_create_events(self):
        member = self.create_user("member_01", "Youth Member")
        response = self.post(
            member,
            "/events",
            {"title": "Youth night", "event_date": date.today().isoformat()},
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"Coming up", member.get("/").data)

        leader = self.create_user("leader_01", "Leader")
        response = self.post(
            leader,
            "/events",
            {
                "title": "Youth night",
                "description": "See you there!",
                "event_date": date.today().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(b"Youth night", leader.get("/calendar").data)
        self.assertIn(b"Youth night", leader.get("/").data)

    def test_gallery_is_disabled_by_default_and_day_limited_when_enabled(self):
        self.assertEqual(self.client.get("/gallery").status_code, 404)
        member = self.create_user("member_02", "Youth Member")
        self.assertNotIn(b"Gallery", member.get("/").data)
        self.app.config["GALLERY_ENABLED"] = True
        response = self.post(
            member,
            "/gallery/open",
            {"gallery_date": date.today().isoformat()},
        )
        self.assertEqual(response.status_code, 403)

        leader = self.create_user("leader_02", "Leader")
        today = date.today().isoformat()
        self.assertEqual(
            self.post(leader, "/gallery/open", {"gallery_date": today}).status_code,
            302,
        )
        response = self.post(
            member,
            f"/gallery/{today}",
            {"photo": (io.BytesIO(PIXEL_PNG), "photo.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(b"Added by member_02", member.get(f"/gallery/{today}").data)
        self.assertEqual(member.get("/gallery/2020-01-01").status_code, 404)
        with self.app.app_context():
            leader_id = get_db().execute(
                "SELECT id FROM users WHERE username = 'leader_02'"
            ).fetchone()["id"]
            get_db().execute(
                "INSERT INTO gallery_days (gallery_date, opened_by) VALUES (?, ?)",
                ("2020-01-01", leader_id),
            )
            get_db().commit()
        closed_response = self.post(
            member,
            "/gallery/2020-01-01",
            {"photo": (io.BytesIO(PIXEL_PNG), "closed.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(closed_response.status_code, 403)

    def test_admin_can_assign_roles_and_block_accounts(self):
        member = self.create_user("admin_target")
        self.assertEqual(member.get("/admin/users").status_code, 403)

        admin = self.app.test_client()
        self.post(
            admin,
            "/login",
            {"username": "youth_app_admin", "password": "test-admin-password"},
        )
        self.assertEqual(admin.get("/admin/users").status_code, 200)
        with self.app.app_context():
            user_id = get_db().execute(
                "SELECT id FROM users WHERE username = 'admin_target'"
            ).fetchone()["id"]
        response = self.post(
            admin,
            f"/admin/users/{user_id}/role",
            {"role": "Leader"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.post(
            member,
            "/events",
            {"title": "Leader event", "event_date": date.today().isoformat()},
        ).status_code, 302)
        self.assertEqual(
            self.post(
                admin,
                f"/admin/users/{user_id}/role",
                {"role": "Youth Member"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.post(
                member,
                "/events",
                {"title": "No longer a leader", "event_date": date.today().isoformat()},
            ).status_code,
            403,
        )

        self.assertEqual(
            self.post(admin, f"/admin/users/{user_id}/block").status_code,
            302,
        )
        self.assertEqual(member.get("/calendar").status_code, 302)
        self.post(member, "/logout")
        response = self.post(
            member,
            "/login",
            {"username": "admin_target", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This account is blocked", response.data)

    def test_only_admin_account_can_open_admin_page(self):
        member = self.create_user("regular_01")
        self.assertEqual(member.get("/admin/users").status_code, 403)
        admin = self.app.test_client()
        self.post(
            admin,
            "/login",
            {"username": "youth_app_admin", "password": "test-admin-password"},
        )
        self.assertIn(b"Admin", admin.get("/").data)
        self.assertNotIn(b"Gallery", admin.get("/").data)

    def test_startup_migrates_existing_database_and_assigns_default_member_role(self):
        legacy_path = os.path.join(self.temp_dir.name, "legacy.sqlite")
        with closing(sqlite3.connect(legacy_path)) as legacy_db, legacy_db:
            legacy_db.execute(
                """
                CREATE TABLE users (
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
                )
                """
            )
            legacy_db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, NULL)",
                ("legacy_member", "existing-hash"),
            )

        migrated_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "migration-test-secret",
                "DATABASE": legacy_path,
                "UPLOAD_FOLDER": os.path.join(self.temp_dir.name, "legacy-uploads"),
                "ADMIN_PASSWORD": "",
            }
        )
        with migrated_app.app_context():
            user = get_db().execute(
                "SELECT role, is_admin, is_blocked FROM users WHERE username = ?",
                ("legacy_member",),
            ).fetchone()
            self.assertEqual(tuple(user), ("Youth Member", 0, 0))

    def test_community_map_saves_approximate_neighborhood(self):
        member = self.create_user("neighbor_01", "Youth Member")
        response = self.post(
            member,
            "/map",
            {
                "postal_code": "80331",
                "area": "Altstadt",
                "latitude": "48.137",
                "longitude": "11.575",
            },
        )
        self.assertEqual(response.status_code, 302)
        page = member.get("/map")
        self.assertIn(b"Altstadt", page.data)
        self.assertIn(b"80331", page.data)
        with self.app.app_context():
            person = get_db().execute(
                "SELECT latitude, longitude FROM users WHERE username = 'neighbor_01'"
            ).fetchone()
            self.assertEqual((person["latitude"], person["longitude"]), (48.137, 11.575))

    def test_qr_code_and_security_headers(self):
        response = self.client.get("/share/qr.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")


if __name__ == "__main__":
    unittest.main()
