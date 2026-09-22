# Freedom Park Booking Web Application

Freedom Park is a mobile-first booking and operations web application built with Flask.

## Architecture

### Frontend
- HTML/Jinja templates in `templates/`
- CSS in `static/css/`
- Browser JavaScript in `static/js/`
- Images in `static/images/`

### Backend
- Python + Flask in `app/`
- Flask blueprints in `app/routes/`
- Business services in `app/services/`
- SQLAlchemy models in `app/models/`
- Shared utilities in `app/utils/`

`run.py` is the small root WSGI entrypoint used to start the backend.

## Local run

```powershell
.\venv\Scripts\Activate.ps1
python run.py
```

Production-style start (Linux/Render):

```bash
gunicorn --bind 0.0.0.0:$PORT "run:app"
```

## Admin booking exports

Admins/System Administrators can download the bookings list as:
- Excel `.xlsx`
- CSV `.csv`

Exports respect the current search, status, and source filters.

## Important

Do not commit real `.env` secrets. SQLite is suitable for local/testing use; production should use persistent database storage.
