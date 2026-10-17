import os
import secrets
from pathlib import Path

from flask import Flask, abort, flash, redirect, request, session, url_for

from .db import close_db, init_db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("DATABASE_PATH")
        or str(Path(app.instance_path) / "youth.sqlite"),
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER")
        or str(Path(app.instance_path) / "uploads"),
        APP_BASE_URL=os.environ.get(
            "APP_BASE_URL", "https://icf-muenchen-youth-app.onrender.com"
        ),
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "youth_app_admin"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", ""),
        GALLERY_ENABLED=os.environ.get("GALLERY_ENABLED", "false").lower()
        in {"1", "true", "yes"},
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("APP_COOKIE_SECURE", "").lower()
        in {"1", "true", "yes"},
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    init_db(app)

    from .routes import bp

    app.register_blueprint(bp)

    @app.before_request
    def protect_form_posts():
        if (
            not app.config["GALLERY_ENABLED"]
            and request.endpoint
            and request.endpoint.startswith("main.")
            and request.endpoint in {
                "main.gallery",
                "main.open_gallery_day",
                "main.gallery_day",
            }
        ):
            abort(404)
        if request.method != "POST":
            return
        from .routes import verify_csrf

        if not verify_csrf(request.form.get("csrf_token", "")):
            abort(400, description="Your form expired. Reload the page and try again.")

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "script-src 'self' https://unpkg.com; "
            "connect-src 'self' https://nominatim.openstreetmap.org; "
            "font-src 'self' https://unpkg.com; frame-ancestors 'none'",
        )
        return response

    @app.context_processor
    def inject_app_settings():
        return {"gallery_enabled": app.config["GALLERY_ENABLED"]}

    @app.template_filter("pretty_date")
    def pretty_date(value):
        from datetime import date

        parsed = date.fromisoformat(value)
        return parsed.strftime("%-d %B %Y")

    @app.template_filter("month_name")
    def month_name(value):
        import calendar

        return calendar.month_abbr[int(value)]

    @app.context_processor
    def inject_today():
        from datetime import date

        return {"today": date.today()}

    return app
