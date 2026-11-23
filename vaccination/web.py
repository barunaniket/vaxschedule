"""HTTP routes. Each module owner keeps their routes in their own section."""
import hmac
from datetime import date
from functools import wraps

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   session, url_for)
from flask import request

from . import scheduling
from .rules import parse_date
from .rules import (VACCINES, NotFoundError, VaccinationError,
                    next_dose_date)
from . import registration
from . import records

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


# --- Module 1: registration (FR-001) ----------------------------------------
def _start_citizen_session(row):
    session.clear()
    session["role"] = "citizen"
    session["citizen_id"] = row["id"]
    session["name"] = row["name"]


@bp.route("/register", methods=["POST"])
def register():
    """Create an account and log the citizen in."""
    form = request.form
    try:
        citizen_id = registration.register_citizen(
            _conn(), form.get("name"), form.get("dob"),
            form.get("id_number"), form.get("mobile"), today=_today())
    except VaccinationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("web.home"))
    _start_citizen_session(registration.get_citizen(_conn(), citizen_id))
    flash("Registration successful.", "success")
    return redirect(url_for("web.citizen"))


@bp.route("/login", methods=["POST"])
def login():
    """Log in with ID number and mobile."""
    try:
        row = registration.find_by_login(
            _conn(), request.form.get("id_number"),
            request.form.get("mobile"))
    except VaccinationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("web.home"))
    _start_citizen_session(row)
    return redirect(url_for("web.citizen"))


@bp.route("/logout")
def logout():
    """End the session."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("web.home"))


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


# --- Module 3: officer records (FR-004) -------------------------------------
@bp.route("/officer/login", methods=["GET", "POST"])
def officer_login():
    """Officers log in with the shared access code."""
    if request.method == "POST":
        code = request.form.get("code", "")
        expected = current_app.config["OFFICER_CODE"]
        if hmac.compare_digest(code.encode(), expected.encode()):
            session.clear()
            session["role"] = "officer"
            return redirect(url_for("web.officer"))
        flash("Wrong officer code.", "error")
    return render_template("officer_login.html")


@bp.route("/officer")
@require_role("officer")
def officer():
    """Bookings for a day plus the publish-slot form."""
    conn = _conn()
    try:
        day = parse_date(request.args.get("day") or _today())
    except VaccinationError as exc:
        flash(str(exc), "error")
        day = _today()
    return render_template(
        "officer.html", day=day.isoformat(),
        bookings=records.bookings_for_day(conn, day),
        centres=scheduling.list_centres(conn), vaccines=list(VACCINES))


@bp.route("/officer/record/<int:booking_id>", methods=["POST"])
@require_role("officer")
def officer_record(booking_id):
    """Record the dose given, then issue the certificate."""
    conn = _conn()
    day = request.form.get("day", "")
    try:
        dose_id = records.record_dose(
            conn, booking_id, request.form.get("batch"))
        flash(f"Dose recorded for booking #{booking_id} "
              f"(dose record #{dose_id}).", "success")
    except VaccinationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web.officer", day=day or None))


@bp.route("/officer/slot", methods=["POST"])
@require_role("officer")
def officer_slot():
    """Publish a new slot."""
    form = request.form
    try:
        scheduling.add_slot(_conn(), form.get("centre_id"), form.get("date"),
                            form.get("vaccine"), form.get("capacity"))
        flash("Slot published.", "success")
    except VaccinationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web.officer", day=form.get("date") or None))
