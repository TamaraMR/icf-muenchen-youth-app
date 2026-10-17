import calendar
import hmac
import io
import re
import secrets
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import qrcode
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from PIL import Image, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("main", __name__)
IMAGE_FORMATS = {"PNG": "PNG", "JPEG": "JPEG", "WEBP": "WEBP"}


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def verify_csrf(token):
    expected = session.get("_csrf_token", "")
    return bool(expected) and hmac.compare_digest(expected, token)


@bp.app_context_processor
def inject_template_values():
    return {"csrf_token": csrf_token}


@bp.before_app_request
def load_user():
    user_id = session.get("user_id")
    g.user = (
        get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user_id
        else None
    )


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Sign in to continue.", "info")
            return redirect(url_for("main.login", next=request.path))
        if g.user["role"] is None and request.endpoint != "main.choose_role":
            return redirect(url_for("main.choose_role"))
        return view(*args, **kwargs)

    return wrapped


def leader_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Sign in to continue.", "info")
            return redirect(url_for("main.login", next=request.path))
        if g.user["role"] is None:
            return redirect(url_for("main.choose_role"))
        if g.user["role"] != "Leader":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def save_image(upload):
    if not upload or not upload.filename:
        return None
    raw = upload.stream.read()
    if not raw or len(raw) > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("Choose an image smaller than 8 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in IMAGE_FORMATS:
                raise ValueError("Please upload a PNG, JPG, or WebP image.")
            if image.width * image.height > 24_000_000:
                raise ValueError("That image is too large to process.")
            image.load()
            image.thumbnail((1800, 1800))
            normalized = image.convert("RGB") if image.mode not in {"RGB", "RGBA"} else image
            filename = f"{uuid4().hex}.png"
            destination = Path(current_app.config["UPLOAD_FOLDER"]) / filename
            normalized.save(destination, format="PNG", optimize=True)
            return filename
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("We could not read that image. Please try a PNG, JPG, or WebP file.") from error


def safe_month():
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        if not 2000 <= year <= 2100 or not 1 <= month <= 12:
            raise ValueError
        return year, month
    except (TypeError, ValueError):
        abort(400, description="Choose a valid calendar month.")


@bp.route("/")
def index():
    if g.user is None:
        return render_template("landing.html")
    if g.user["role"] is None:
        return redirect(url_for("main.choose_role"))

    events = get_db().execute(
        "SELECT title, description, event_date FROM events "
        "WHERE event_date >= ? ORDER BY event_date, id LIMIT 3",
        (date.today().isoformat(),),
    ).fetchall()
    return render_template("home.html", events=events)


@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        problem = None
        if not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
            problem = "Choose a username with 3–24 letters, numbers, or underscores."
        elif len(password) < 8 or len(password) > 128:
            problem = "Your password must be between 8 and 128 characters."
        if problem:
            flash(problem, "error")
        else:
            try:
                cursor = get_db().execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                get_db().commit()
            except sqlite3.IntegrityError:
                flash("That username is already taken. Try another one.", "error")
            else:
                flash("Your account is ready. Sign in to choose your role.", "success")
                return redirect(url_for("main.login"))
    return render_template("register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("We couldn’t find a matching username and password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            destination = request.args.get("next", "")
            if not destination.startswith("/") or destination.startswith("//"):
                destination = url_for("main.index")
            return redirect(destination)
    return render_template("login.html")


@bp.route("/choose-role", methods=("GET", "POST"))
@login_required
def choose_role():
    if g.user["role"] is not None:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        role = request.form.get("role")
        if role not in {"Youth Member", "Leader"}:
            flash("Choose one of the roles to continue.", "error")
        else:
            get_db().execute("UPDATE users SET role = ? WHERE id = ?", (role, g.user["id"]))
            get_db().commit()
            return redirect(url_for("main.index"))
    return render_template("choose_role.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You’re signed out. See you soon!", "info")
    return redirect(url_for("main.index"))


@bp.post("/profile")
@login_required
def update_profile():
    bio = request.form.get("bio", "").strip()
    birthday = request.form.get("birthday", "").strip() or None
    if len(bio) > 240:
        flash("Keep your bio to 240 characters or fewer.", "error")
        return redirect(url_for("main.index"))
    if birthday:
        try:
            date.fromisoformat(birthday)
        except ValueError:
            flash("Choose a valid birthday.", "error")
            return redirect(url_for("main.index"))
        if birthday > date.today().isoformat():
            flash("Your birthday can’t be in the future.", "error")
            return redirect(url_for("main.index"))

    image_name = g.user["profile_image"]
    upload = request.files.get("profile_image")
    if upload and upload.filename:
        try:
            image_name = save_image(upload)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("main.index"))

    get_db().execute(
        "UPDATE users SET bio = ?, birthday = ?, profile_image = ? WHERE id = ?",
        (bio, birthday, image_name, g.user["id"]),
    )
    get_db().commit()
    flash("Your profile has been updated.", "success")
    return redirect(url_for("main.index"))


@bp.route("/map", methods=("GET", "POST"))
@login_required
def community_map():
    if request.method == "POST":
        postal_code = request.form.get("postal_code", "").strip()
        area = request.form.get("area", "").strip()
        try:
            latitude = float(request.form.get("latitude", ""))
            longitude = float(request.form.get("longitude", ""))
        except ValueError:
            latitude = longitude = None
        if not re.fullmatch(r"\d{5}", postal_code):
            flash("Enter a valid 5-digit German postal code.", "error")
        elif not area or len(area) > 80:
            flash("Add a neighborhood or area (up to 80 characters).", "error")
        elif (
            latitude is None
            or longitude is None
            or not 47 <= latitude <= 49
            or not 10 <= longitude <= 14
        ):
            flash("Tap the map to place an approximate neighborhood pin.", "error")
        else:
            get_db().execute(
                "UPDATE users SET postal_code = ?, area = ?, latitude = ?, longitude = ? "
                "WHERE id = ?",
                (postal_code, area, latitude, longitude, g.user["id"]),
            )
            get_db().commit()
            flash("Your approximate neighborhood has been added to the map.", "success")
            return redirect(url_for("main.community_map"))

    locations = get_db().execute(
        "SELECT id, username, role, bio, birthday, profile_image, postal_code, area, "
        "latitude, longitude "
        "FROM users WHERE latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY username"
    ).fetchall()
    return render_template("map.html", locations=[dict(person) for person in locations])


@bp.route("/info")
@login_required
def information():
    return render_template("info.html")


@bp.route("/calendar")
@login_required
def calendar_page():
    year, month = safe_month()
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    db = get_db()
    events = db.execute(
        "SELECT events.*, users.username AS author FROM events "
        "JOIN users ON users.id = events.created_by "
        "WHERE event_date BETWEEN ? AND ? ORDER BY event_date, title",
        (first_day.isoformat(), last_day.isoformat()),
    ).fetchall()
    birthdays = db.execute(
        "SELECT username, birthday, profile_image FROM users "
        "WHERE birthday IS NOT NULL AND substr(birthday, 6, 2) = ? ORDER BY username",
        (f"{month:02d}",),
    ).fetchall()
    days = {
        day: {"events": [], "birthdays": []}
        for day in range(1, last_day.day + 1)
    }
    for event in events:
        days[int(event["event_date"][8:10])]["events"].append(event)
    for person in birthdays:
        days[int(person["birthday"][8:10])]["birthdays"].append(person)

    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    previous = first_day.replace(day=1).toordinal() - 1
    previous_date = date.fromordinal(previous)
    if month == 12:
        next_date = date(year + 1, 1, 1)
    else:
        next_date = date(year, month + 1, 1)
    return render_template(
        "calendar.html",
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        weeks=weeks,
        days=days,
        today=date.today(),
        previous_year=previous_date.year,
        previous_month=previous_date.month,
        next_year=next_date.year,
        next_month=next_date.month,
    )


@bp.post("/events")
@leader_required
def create_event():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    event_date = request.form.get("event_date", "").strip()
    if not title or len(title) > 90 or len(description) > 500:
        flash("Add an event name (up to 90 characters) and a short description.", "error")
    else:
        try:
            parsed_date = date.fromisoformat(event_date)
        except ValueError:
            parsed_date = None
        if parsed_date is None or parsed_date < date.today():
            flash("Choose a valid date today or later.", "error")
        else:
            get_db().execute(
                "INSERT INTO events (title, description, event_date, created_by) "
                "VALUES (?, ?, ?, ?)",
                (title, description, event_date, g.user["id"]),
            )
            get_db().commit()
            flash("The event is on the calendar.", "success")
            return redirect(url_for("main.calendar_page"))
    return redirect(url_for("main.calendar_page"))


@bp.route("/gallery")
@login_required
def gallery():
    galleries = get_db().execute(
        "SELECT gallery_days.gallery_date, users.username AS opened_by, "
        "COUNT(gallery_photos.id) AS photo_count, MIN(gallery_photos.filename) AS cover "
        "FROM gallery_days JOIN users ON users.id = gallery_days.opened_by "
        "LEFT JOIN gallery_photos ON gallery_photos.gallery_date = gallery_days.gallery_date "
        "GROUP BY gallery_days.gallery_date ORDER BY gallery_days.gallery_date DESC"
    ).fetchall()
    return render_template("gallery.html", galleries=galleries)


@bp.post("/gallery/open")
@leader_required
def open_gallery_day():
    selected_day = request.form.get("gallery_date", "")
    if selected_day != date.today().isoformat():
        flash("A gallery day can only be opened on that day.", "error")
    else:
        cursor = get_db().execute(
            "INSERT OR IGNORE INTO gallery_days (gallery_date, opened_by) VALUES (?, ?)",
            (selected_day, g.user["id"]),
        )
        get_db().commit()
        if cursor.rowcount:
            flash("Today’s gallery is open. Everyone can add a photo until midnight.", "success")
        else:
            flash("Today’s gallery is already open.", "info")
    return redirect(url_for("main.gallery"))


@bp.route("/gallery/<gallery_date>", methods=("GET", "POST"))
@login_required
def gallery_day(gallery_date):
    try:
        parsed_day = date.fromisoformat(gallery_date)
    except ValueError:
        abort(404)
    db = get_db()
    opened = db.execute(
        "SELECT gallery_days.*, users.username AS opened_by FROM gallery_days "
        "JOIN users ON users.id = gallery_days.opened_by WHERE gallery_date = ?",
        (gallery_date,),
    ).fetchone()
    if opened is None:
        abort(404)

    if request.method == "POST":
        if parsed_day != date.today():
            abort(403, description="Photos can only be added on the gallery day.")
        try:
            filename = save_image(request.files.get("photo"))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("main.gallery_day", gallery_date=gallery_date))
        if filename is None:
            flash("Choose a photo to upload.", "error")
            return redirect(url_for("main.gallery_day", gallery_date=gallery_date))
        caption = request.form.get("caption", "").strip()
        if len(caption) > 160:
            (Path(current_app.config["UPLOAD_FOLDER"]) / filename).unlink(missing_ok=True)
            flash("Keep captions to 160 characters or fewer.", "error")
            return redirect(url_for("main.gallery_day", gallery_date=gallery_date))
        db.execute(
            "INSERT INTO gallery_photos (gallery_date, user_id, filename, caption) "
            "VALUES (?, ?, ?, ?)",
            (gallery_date, g.user["id"], filename, caption),
        )
        db.commit()
        flash("Your memory has been added.", "success")
        return redirect(url_for("main.gallery_day", gallery_date=gallery_date))

    photos = db.execute(
        "SELECT gallery_photos.*, users.username FROM gallery_photos "
        "JOIN users ON users.id = gallery_photos.user_id "
        "WHERE gallery_date = ? ORDER BY uploaded_at, id",
        (gallery_date,),
    ).fetchall()
    return render_template(
        "gallery_day.html",
        gallery_date=gallery_date,
        opened=opened,
        photos=photos,
        can_upload=parsed_day == date.today(),
        parsed_day=parsed_day,
    )


@bp.route("/share/qr.png")
def share_qr():
    base_url = (current_app.config.get("APP_BASE_URL") or request.url_root).rstrip("/") + "/"
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        abort(400, description="Set APP_BASE_URL to a valid public app URL.")
    image = qrcode.make(base_url)
    output = io.BytesIO()
    image.save(output, format="PNG")
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "image/png"
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@bp.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    if not re.fullmatch(r"[a-f0-9]{32}\.png", filename):
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
