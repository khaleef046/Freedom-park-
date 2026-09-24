import os
import socket
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from app import create_app
from app.extensions import db

app = create_app()

@app.cli.command("seed")
def seed():
    """Seed initial database with development users, equipment, and settings."""
    import seed
    seed.seed_all()
    print("Database seeding completed successfully.")


@app.cli.command("reset-staff-password")
@click.option("--username", prompt="Staff username", help="Username of the staff account to update.")
def reset_staff_password(username):
    """Set a new password for one existing staff account."""
    from app.models.user import Role, User

    with app.app_context():
        user = User.query.filter_by(username=username.strip()).first()
        if not user or user.role not in Role.STAFF_ROLES:
            raise click.ClickException("No matching staff account was found.")

        password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters long.")

        user.set_password(password)
        db.session.commit()
        click.echo(f"Password updated for staff account '{user.username}'.")

def get_local_ip():
    """Detect local LAN IPv4 address for mobile device testing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    local_ip = get_local_ip()

    print("\n" + "=" * 62)
    print("🌿 FREEDOM PARK WEB PLATFORM — SERVER STARTING")
    print("=" * 62)
    print(f" * Local PC Access:       http://localhost:{port}")
    print(f" * Mobile / Wi-Fi Access: http://{local_ip}:{port}")
    print("=" * 62)
    print("📱 To test on your mobile device:")
    print("   1. Connect your phone to the same Wi-Fi network as this PC.")
    print(f"   2. Open your phone's browser and go to: http://{local_ip}:{port}")
    print("=" * 62 + "\n")

    app.run(host=host, port=port, debug=True)

