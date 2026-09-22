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

The build command is:
`pip install -r requirements.txt`

The start command initializes missing database tables and settings, then starts Gunicorn:
`python scripts/prepare_render.py && gunicorn --bind 0.0.0.0:$PORT "run:app"`

After the first successful deploy, open the Render service Shell and run this once:
`python seed.py`

This creates the initial staff accounts and sample park settings in PostgreSQL. Sign in with the seeded account, change every seeded password immediately, and remove or replace sample content before accepting real bookings.

## Required production settings

Set these in Render if they are not already provided by the blueprint:
- `SECRET_KEY`: a long random value.
- `FLASK_ENV`: `production`.
- `OTP_MOCK_MODE`: `false`.

The current OTP implementation is not connected to an SMS provider. For real customer login, add an SMS/WhatsApp provider and configure its credentials as Render secret environment variables.

Uploaded files use the local filesystem. Render's filesystem is ephemeral, so uploaded
files are not durable across deploys/restarts. Configure object storage before relying
on uploaded content in production. Existing database records are not deleted or reset.
