# ICF Youth München

A responsive community app for ICF Youth München, built with Python, Flask, SQLite, and a small amount of browser JavaScript.

Live website: [https://icf-muenchen-youth-app.onrender.com](https://icf-muenchen-youth-app.onrender.com)

## Deploy on Render

This repository is configured for a Render **Web Service**:

1. Connect the GitHub repository to Render and create a Python web service.
2. Use the following commands:

   ```text
   Build command: pip install -r requirements.txt
   Start command: gunicorn --bind 0.0.0.0:$PORT app:app
   ```

3. Add these environment variables in the Render service settings:

   | Variable | Value |
   | --- | --- |
   | `APP_BASE_URL` | `https://icf-muenchen-youth-app.onrender.com` |
   | `SECRET_KEY` | A long, unique, randomly generated secret |
   | `APP_COOKIE_SECURE` | `1` |
   | `ADMIN_USERNAME` | `youth_app_admin` |
   | `ADMIN_PASSWORD` | A unique secret, entered directly in Render |

   Never put `ADMIN_PASSWORD` or `SECRET_KEY` in this README, source code, or a GitHub commit. The originally requested admin password is a shared, known credential; choose a new private password before using the live site. The first time the service starts with `ADMIN_PASSWORD` set, it creates the administrator account. Keep that value unchanged on subsequent deploys; changing it in Render does not automatically rotate an already-created account's database password.

4. Deploy, then open the website and visit `/share/qr.png` to download a QR code pointing to the public site. The homepage also shows the QR code. It uses `APP_BASE_URL`, not the server's local `127.0.0.1` address.

To run locally, create a virtual environment, install `requirements.txt`, set `ADMIN_PASSWORD` and `SECRET_KEY`, and start the development server with `flask --app app run`.

## Render free-plan storage note

Render's free web-service filesystem is ephemeral. This app currently stores its SQLite database and uploaded profile images under `instance/`, so accounts and uploaded photos can be lost when the free service restarts, redeploys, or spins down. A QR code and public URL do **not** make that data persistent. Do not rely on the free instance as the only copy of important community data. Durable storage requires moving the database and uploads to persistent services (for example, managed PostgreSQL plus object storage) or using a hosting plan with a persistent disk and configuring `DATABASE_PATH` and `UPLOAD_FOLDER` accordingly.

The Render free service may also spin down while idle; the first request after inactivity can take a little while to load.

## Features

- Account registration uses unique usernames and password hashes. New accounts are ordinary **Youth Member** accounts; users cannot select their role.
- The configured administrator can view accounts, assign or remove Leader access, and block or unblock accounts at `/admin/users`.
- Members can update their profile photo, bio, birthday, and approximate neighborhood. The home page shows the next three upcoming events when available.
- Everyone can add a birthday; only Leaders can add calendar events.
- The community map displays member profile photos or initials and opens a profile popup. To place a pin, the map automatically looks up the entered postcode and area through OpenStreetMap Nominatim. It does not require a manual map click. The entered location is approximate, and the postcode and area are sent to that public geocoding service to determine coordinates.
- German/English language buttons are available in the top-right navigation. The selection is saved in the browser.
- The QR code is generated locally by `/share/qr.png`.

### Gallery temporarily disabled

The gallery routes, templates, and upload handling are retained in the project, but the gallery is disabled by default. To restore it, set `GALLERY_ENABLED=true` in Render (or the local environment) and redeploy. The navigation and home-page link reappear automatically. The gallery rule remains: Leaders open a gallery for the current day, uploads close at the end of that day, and old galleries remain viewable.

## Project structure

```text
app.py                         Flask entry point
youth_app/
  __init__.py                  App factory, configuration, request security
  db.py                        SQLite schema, upgrades, admin bootstrap
  routes.py                    Authentication, profile, map, calendar, admin, gallery
  templates/                   Jinja pages and shared layout
  static/
    css/app.css                Responsive styles
    js/language.js             Browser language switch and translations
    js/map.js                  Leaflet map and postcode geocoding
    images/youth-logo.png      ICF Youth logo
tests/
  test_app.py                  Authentication, permissions, and feature tests
instance/                      Local SQLite database and image uploads
```

## Privacy and production

Neighborhood pins are approximate and must not be used for street addresses. Map tiles and postcode geocoding are provided by public OpenStreetMap services; Leaflet is loaded from its CDN. The admin password, session secret, and user data must be handled as private information. The default Flask development server is for local testing only; Render uses Gunicorn.
