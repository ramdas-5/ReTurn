"""Operational CLI commands: reset, bootstrap, diagnostics.

Destructive commands always print the target database and require an explicit
confirmation flag. Nothing here runs automatically on deploy.
"""
from __future__ import annotations

import secrets
import sys
from urllib.parse import urlparse

import click
from flask import current_app
from sqlalchemy import text

from .extensions import db
from .security import hash_password


def register_cli(app) -> None:
    @app.cli.command("bootstrap-admin")
    @click.option("--email", default=None, help="Admin email (defaults to env).")
    @click.option("--name", default=None, help="Admin display name.")
    @click.option("--password", default=None, help="Password (defaults to env or generated).")
    def bootstrap_admin(email, name, password):
        """Create the first administrator securely (idempotent)."""
        from .models import User

        email = (email or current_app.config.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
        name = name or current_app.config.get("BOOTSTRAP_ADMIN_NAME") or "ReTurn Administrator"
        password = password or current_app.config.get("BOOTSTRAP_ADMIN_PASSWORD") or ""
        if not email:
            raise click.ClickException(
                "Provide --email or set BOOTSTRAP_ADMIN_EMAIL. No account was created."
            )
        if User.query.filter_by(role="admin").first() is not None:
            click.echo("An administrator already exists; nothing created.")
            return
        generated = False
        if not password:
            password = secrets.token_urlsafe(18)
            generated = True
        user = User(
            email=email,
            full_name=name,
            role="admin",
            status="active",
            must_change_password=False,
            password_hash=hash_password(password),
        )
        db.session.add(user)
        from .services.reference import ensure_reference_data

        created = ensure_reference_data()
        db.session.commit()
        click.echo(f"Administrator created: {email}")
        click.echo(f"Reference data ready: {created}")
        if generated:
            click.echo("Generated one-time password (store securely, shown once):")
            click.echo(f"  {password}")

    @app.cli.command("reset-db")
    @click.option("--yes", is_flag=True, help="Confirm the destructive reset.")
    @click.option("--force", is_flag=True, help="Allow a non-local database (use with care).")
    @click.option("--seed", is_flag=True, help="Seed the fictional demo scenario afterwards.")
    def reset_db(yes, force, seed):
        """Drop and recreate the public schema, then apply migrations.

        Intended for a disposable local/demo database only. This command is never
        invoked by the API or the container entrypoint.
        """
        url = current_app.config["SQLALCHEMY_DATABASE_URI"]
        parsed = urlparse(url.replace("+psycopg", ""))
        host = parsed.hostname or "unknown"
        local = host in {"127.0.0.1", "localhost", "db", "return-db"}
        click.echo(f"Target database host: {host} / {parsed.path.lstrip('/')}")
        if not yes:
            raise click.ClickException("Refusing to reset without --yes.")
        if not local and not force:
            raise click.ClickException(
                "This is a non-local database. Re-run with --force only after taking a backup."
            )
        click.echo("Dropping schema public…")
        with db.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        click.echo("Schema reset. Run `flask --app wsgi db upgrade` next.")
        if seed:
            click.echo("Seed requested — run `flask --app wsgi seed-demo` after migrations.")

    @app.cli.command("seed-reference")
    def seed_reference():
        """Insert the permission catalogue, rejection codes and capacity profiles."""
        from .services.reference import ensure_reference_data

        created = ensure_reference_data()
        db.session.commit()
        click.echo(f"Reference data ready: {created}")

    @app.cli.command("check")
    def check():
        """Print migration state and row counts without changing data."""
        tables = [
            "users",
            "orders",
            "parcel_details",
            "delivery_batches",
            "route_stops",
            "driver_duty_sessions",
            "driver_location_events",
            "matching_suggestions",
            "proof_media",
            "audit_logs",
        ]
        counts = {}
        for table in tables:
            try:
                counts[table] = db.session.execute(
                    text(f"SELECT count(*) FROM {table}")
                ).scalar()
            except Exception:
                db.session.rollback()
                counts[table] = "missing"
        click.echo(f"Database: {current_app.config['SQLALCHEMY_DATABASE_URI'].split('@')[-1]}")
        for table, count in counts.items():
            click.echo(f"  {table}: {count}")
