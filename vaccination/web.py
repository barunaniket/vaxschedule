"""HTTP routes. Each module owner keeps their routes in their own section."""
from datetime import date
from functools import wraps

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   session, url_for)
from flask import request

from . import scheduling
from .rules import parse_date
from .rules import (VACCINES, NotFoundError, VaccinationError,
                    next_dose_date)

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


# --- Module 2: booking (FR-002, FR-003) -------------------------------------
def _vaccination_status(doses):
    if not doses:
        return "NOT VACCINATED", None
    vaccine = doses[0]["vaccine"]
    if len(doses) >= VACCINES[vaccine]["doses"]:
        return "FULLY VACCINATED", None
    return "PARTIALLY VACCINATED", next_dose_date(
        vaccine, doses[-1]["date_given"])


@bp.route("/citizen")
@require_role("citizen")
def citizen():
    """Citizen dashboard: doses, current booking and free slots."""
    conn = _conn()
    citizen_id = session["citizen_id"]
    doses = scheduling.doses_taken(conn, citizen_id)
    status, next_due = _vaccination_status(doses)
    pincode = request.args.get("pincode", "").strip()
    slots = scheduling.search_slots(conn, pincode or None, _today())
    return render_template(
        "citizen.html", name=session.get("name", ""), doses=doses,
        status=status, next_due=next_due, pincode=pincode, slots=slots,
        booking=scheduling.active_booking(conn, citizen_id))


@bp.route("/book/<int:slot_id>", methods=["POST"])
@require_role("citizen")
def book(slot_id):
    """Book the next dose in a slot."""
    try:
        booking_id = scheduling.book_slot(
            _conn(), session["citizen_id"], slot_id, today=_today())
        flash(f"Slot booked (booking #{booking_id}).", "success")
    except VaccinationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web.citizen"))


@bp.route("/cancel/<int:booking_id>", methods=["POST"])
@require_role("citizen")
def cancel(booking_id):
    """Cancel one of the citizen's own bookings."""
    conn = _conn()
    try:
        booking = scheduling.get_booking(conn, booking_id)
        if booking["citizen_id"] != session["citizen_id"]:
            # Don't reveal that someone else's booking exists.
            raise NotFoundError(
                f"Booking {booking_id} not found.")
        scheduling.cancel_booking(conn, booking_id)
        flash("Booking cancelled.", "success")
    except VaccinationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web.citizen"))
