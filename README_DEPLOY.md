# Freedom Park — Render Deployment

This version is flattened so the project can be deployed from the project root.

## Structure
- `app/` — Flask backend
- `templates/` — HTML frontend
- `static/` — CSS/JS/images
- `run.py` — Flask entry point
- `requirements.txt` — Python dependencies
- `render.yaml` — Render configuration

## Local
```powershell
cd "D:\FreedomPark_EasyDeploy"
pip install -r requirements.txt
python run.py
```

## Render Free

The included `render.yaml` creates one free web service running Gunicorn. Render's
database in the previous configuration was a paid Basic PostgreSQL instance, so
this free deployment expects a free-tier external PostgreSQL database instead.

1. Create a free PostgreSQL database with a provider such as Neon or Supabase.
2. Copy its private connection string; do not commit it.
3. In Render, choose **New > Blueprint**, connect this repository, and apply the blueprint.
4. Set the Render `DATABASE_URL` secret to that PostgreSQL connection string.
5. Render generates `SECRET_KEY`; keep it private and never replace it with a development value.

Production refuses to start without both `DATABASE_URL` and `SECRET_KEY`. This prevents
bookings and users from being written to Render's ephemeral local filesystem.
The current local SQLite database is not copied automatically; migrate its data to the
external PostgreSQL database before accepting real bookings.

The Blueprint installs dependencies during build. At service start it applies Alembic
migrations, inserts only missing default settings, and starts Gunicorn on Render's port:
`pip install -r requirements.txt`
`python -m flask --app run:app db upgrade && python scripts/prepare_render.py && gunicorn --bind 0.0.0.0:$PORT wsgi:app`

Do not run `python seed.py` against production. It is a development seeder that creates
accounts with fixed source-controlled passwords and sample content. Provision the first
production staff account through a separately secured process before relying on protected
staff/admin workflows; this repository does not yet provide a production-safe bootstrap command.

## Required production settings

Set these in Render if they are not already provided by the blueprint:
- `SECRET_KEY`: a long random value.
- `FLASK_ENV`: `production`.
- `OTP_MOCK_MODE`: `false`.
- `GOOGLE_CLIENT_ID`: OAuth 2.0 Client ID from Google Cloud Console.
- `GOOGLE_CLIENT_SECRET`: OAuth 2.0 Client Secret from Google Cloud Console.
- `GOOGLE_REDIRECT_URI`: exact HTTPS callback URL for the Render service, ending in `/auth/google/callback`.

For local Google OAuth, set `GOOGLE_REDIRECT_URI` to
`http://localhost:5000/auth/google/callback`. In Google Cloud Console, register the exact
local and production callback URLs under **Authorized redirect URIs**. Configure the
production HTTPS URL after Render assigns the service hostname.

The current OTP implementation is not connected to an SMS provider. For real customer login, add an SMS/WhatsApp provider and configure its credentials as Render secret environment variables.

Uploaded files use the local filesystem. Render's filesystem is ephemeral, so uploaded
files are not durable across deploys/restarts. Configure object storage before relying
on uploaded content in production. Existing database records are not deleted or reset.
