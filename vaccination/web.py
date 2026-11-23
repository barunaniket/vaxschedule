"""HTTP routes. Each module owner keeps their routes in their own section."""
from datetime import date
from functools import wraps

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   session, url_for)

from .rules import parse_date

bp = Blueprint("web", __name__)


# --- Shared helpers ---------------------------------------------------------
def _conn():
    return current_app.extensions["db"]


def _today():
    fixed = current_app.config.get("TODAY")
    return parse_date(fixed) if fixed else date.today()


def require_role(role):
    """Only let users whose session has ``role`` through (NFR-002)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
                flash("Please log in first.", "error")
                return redirect(url_for("web.home"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@bp.route("/")
def home():
    """Landing page."""
    return render_template("home.html")
