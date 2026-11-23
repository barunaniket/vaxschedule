"""VaxSchedule: vaccination cohort and dose scheduling system."""
import os

from flask import Flask

from . import db


def create_app(config=None):
    """Application factory.

    Settings come from environment variables (with development defaults)
    and can be overridden by the ``config`` mapping, which tests use.
    """
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        CERT_SECRET=os.environ.get("CERT_SECRET", "dev-cert-key"),
        OFFICER_CODE=os.environ.get("OFFICER_CODE", "officer123"),
        DATABASE=os.environ.get("DATABASE", "vaccination.db"),
        TODAY=os.environ.get("TODAY"),
    )
    if config:
        app.config.update(config)

    app.extensions["db"] = db.connect(app.config["DATABASE"])

    from . import web  # pylint: disable=import-outside-toplevel
    app.register_blueprint(web.bp)
    return app
