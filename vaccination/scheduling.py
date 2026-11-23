"""FR-002 / FR-003: centres, slots, booking and the dose-interval rule."""
from datetime import date

from .rules import (NotFoundError, RuleViolation, ValidationError,
                    check_dose_interval, is_fully_vaccinated, parse_date,
                    validate_vaccine)


def add_centre(conn, name, district, pincode):
    """Create a vaccination centre. The PIN code must be 6 digits."""
    name = (name or "").strip()
    district = (district or "").strip()
    pincode = (pincode or "").strip()
    if not name or not district:
        raise ValidationError("Centre name and district are required.")
    if len(pincode) != 6 or not pincode.isdigit():
        raise ValidationError("PIN code must be 6 digits.")
    with conn:
        cur = conn.execute(
            "INSERT INTO centres (name, district, pincode) VALUES (?, ?, ?)",
            (name, district, pincode))
    return cur.lastrowid


def list_centres(conn):
    """All centres, by name."""
    return conn.execute("SELECT * FROM centres ORDER BY name").fetchall()


def add_slot(conn, centre_id, day, vaccine, capacity):
    """Publish a slot at a centre for one day and one vaccine."""
    validate_vaccine(vaccine)
    day = parse_date(day)
    try:
        capacity = int(capacity)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Capacity must be a whole number.") from exc
    if capacity <= 0:
        raise ValidationError("Capacity must be positive.")
    centre = conn.execute(
        "SELECT id FROM centres WHERE id = ?", (centre_id,)).fetchone()
    if centre is None:
        raise NotFoundError(f"Centre {centre_id} not found.")
    with conn:
        cur = conn.execute(
            "INSERT INTO slots (centre_id, date, vaccine, capacity) "
            "VALUES (?, ?, ?, ?)",
            (centre_id, day.isoformat(), vaccine, capacity))
    return cur.lastrowid


def search_slots(conn, pincode=None, from_day=None):
    """Slots that still have free places, optionally filtered."""
    pincode = (pincode or "").strip() or None
    from_day = parse_date(from_day).isoformat() if from_day else None
    return conn.execute(
        "SELECT s.id, s.date, s.vaccine, s.capacity, s.booked, "
        "       s.capacity - s.booked AS free, "
        "       c.name AS centre, c.district, c.pincode "
        "FROM slots s JOIN centres c ON c.id = s.centre_id "
        "WHERE s.booked < s.capacity "
        "  AND (? IS NULL OR c.pincode = ?) "
        "  AND (? IS NULL OR s.date >= ?) "
        "ORDER BY s.date, c.name, s.id",
        (pincode, pincode, from_day, from_day)).fetchall()


def doses_taken(conn, citizen_id):
    """Doses a citizen has received, in order."""
    return conn.execute(
        "SELECT * FROM doses WHERE citizen_id = ? ORDER BY dose_number",
        (citizen_id,)).fetchall()


def active_booking(conn, citizen_id):
    """The citizen's current BOOKED booking, or ``None``."""
    return conn.execute(
        "SELECT b.*, s.date, s.vaccine, c.name AS centre "
        "FROM bookings b JOIN slots s ON s.id = b.slot_id "
        "JOIN centres c ON c.id = s.centre_id "
        "WHERE b.citizen_id = ? AND b.status = 'BOOKED'",
        (citizen_id,)).fetchone()


def get_booking(conn, booking_id):
    """Fetch one booking or raise ``NotFoundError``."""
    row = conn.execute(
        "SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Booking {booking_id} not found.")
    return row


def _check_next_dose(doses, slot, slot_day):
    """Rules for Dose 2 onwards (FR-003)."""
    vaccine = doses[0]["vaccine"]
    if is_fully_vaccinated(vaccine, len(doses)):
        raise RuleViolation("You are already fully vaccinated.")
    if slot["vaccine"] != vaccine:
        raise RuleViolation(
            f"Later doses must use the same vaccine ({vaccine}).")
    check_dose_interval(vaccine, doses[-1]["date_given"], slot_day)


def book_slot(conn, citizen_id, slot_id, today=None):
    """Book the citizen's next dose in a slot. Returns the booking id."""
    today = today or date.today()
    citizen = conn.execute(
        "SELECT id FROM citizens WHERE id = ?", (citizen_id,)).fetchone()
    if citizen is None:
        raise NotFoundError(f"Citizen {citizen_id} not found.")
    slot = conn.execute(
        "SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
    if slot is None:
        raise NotFoundError(f"Slot {slot_id} not found.")

    slot_day = parse_date(slot["date"])
    if slot_day < today:
        raise RuleViolation("This slot is in the past.")
    if slot["booked"] >= slot["capacity"]:
        raise RuleViolation("Slot is full.")
    if active_booking(conn, citizen_id) is not None:
        raise RuleViolation(
            "You already have an active booking. Cancel it first.")

    doses = doses_taken(conn, citizen_id)
    if doses:
        _check_next_dose(doses, slot, slot_day)

    # Atomic: only succeeds while a place is still free (NFR-004).
    cur = conn.execute(
        "UPDATE slots SET booked = booked + 1 "
        "WHERE id = ? AND booked < capacity", (slot_id,))
    if cur.rowcount == 0:
        conn.rollback()
        raise RuleViolation("Slot is full.")
    cur = conn.execute(
        "INSERT INTO bookings (citizen_id, slot_id, dose_number) "
        "VALUES (?, ?, ?)", (citizen_id, slot_id, len(doses) + 1))
    conn.commit()
    return cur.lastrowid


def cancel_booking(conn, booking_id):
    """Cancel an active booking and free its place."""
    booking = get_booking(conn, booking_id)
    if booking["status"] != "BOOKED":
        raise RuleViolation("Only active bookings can be cancelled.")
    with conn:
        conn.execute(
            "UPDATE bookings SET status = 'CANCELLED' WHERE id = ?",
            (booking_id,))
        conn.execute(
            "UPDATE slots SET booked = booked - 1 "
            "WHERE id = ? AND booked > 0", (booking["slot_id"],))
