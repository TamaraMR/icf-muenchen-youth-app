# ICF Youth München

A responsive community app for ICF Youth München, built with Python, Flask, SQLite, and a small amount of browser JavaScript. Members can share a neighborhood pin, birthdays, and memories; leaders can publish community events and open the day’s photo gallery.

## Run locally

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open the local address printed by Flask (usually `http://127.0.0.1:5000`). The SQLite database and uploaded images are created under `instance/` on first run. To share the app, deploy it to a publicly reachable HTTPS address; the QR code and “Share the app” link point to the current address. For deployments behind a proxy or with a custom domain, set `APP_BASE_URL` to the public site URL.

Set a stable random `SECRET_KEY` in the environment for deployments. Set `APP_COOKIE_SECURE=1` when serving over HTTPS. For a custom database or upload location, set `DATABASE_PATH` or `UPLOAD_FOLDER`. The built-in Flask server is intended for local development; use a production WSGI server and HTTPS for deployment.

To run the tests:

```bash
python -m unittest discover -s tests -v
```

## App structure

```text
app.py                         Flask entry point
youth_app/
  __init__.py                  App factory, configuration, request security
  db.py                        SQLite schema and connection lifecycle
  routes.py                    Authentication and feature routes
  templates/                   Jinja pages and shared layout
  static/
    css/app.css                Responsive design system and page styles
    js/map.js                  Leaflet map and approximate pin placement
    images/youth-logo.png      Provided ICF Youth logo
tests/
  test_app.py                  Authentication, permissions, and feature tests
instance/                      Local database and private uploads (not committed)
```

## Features and permissions

- Registration requires a unique username and a password of at least eight characters. On first sign-in, people select either **Youth Member** or **Leader**.
- Everyone can update their bio, optional profile photo, birthday, and approximate neighborhood. The map uses OpenStreetMap tiles and Leaflet; members click the map to place a general pin, and other members can view the area and postcode and open a profile popup. Do not enter a street address.
- Everyone can add their own birthday. Leaders can add future community events; the homepage shows the next three when available.
- Leaders can open a gallery only for the current day. Any signed-in member can upload an image to that open gallery on that day; albums are read-only after the day ends and remain available to browse.
- Images are decoded and normalized before storage. Profile photos and gallery images are available only to signed-in users.
- A QR code is generated locally for the current public app URL, without sending it to a third-party QR service.

**Prototype note:** role selection is self-service to match the first-login flow. Before using this app with a wider public audience, change Leader assignment to an invitation or administrator approval workflow.

## Privacy and external services

Neighborhood markers are approximate, and the map displays only a member’s chosen area and postcode. The map uses OpenStreetMap’s public tile service and Leaflet’s CDN, so browsers need an internet connection to load map tiles; accounts, profile data, events, and uploaded photos remain in the app’s SQLite database and upload directory.
