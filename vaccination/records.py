"""FR-004: officer view of bookings and recording the dose given."""
from .rules import NotFoundError, RuleViolation, ValidationError, parse_date


def bookings_for_day(conn, day):
    """Active and completed bookings on one day, for the officer console."""
    return conn.execute(
        "SELECT b.id, b.dose_number, b.status, z.name, z.id_number, "
        "       s.vaccine, s.date, c.name AS centre "
        "FROM bookings b "
        "JOIN citizens z ON z.id = b.citizen_id "
        "JOIN slots s ON s.id = b.slot_id "
        "JOIN centres c ON c.id = s.centre_id "
        "WHERE s.date = ? AND b.status != 'CANCELLED' "
        "ORDER BY c.name, b.id",
        (parse_date(day).isoformat(),)).fetchall()


def record_dose(conn, booking_id, batch):
    """Record the dose for a BOOKED booking. Returns the dose id."""
    batch = (batch or "").strip().upper()
    if not batch:
        raise ValidationError("Batch number is required.")
    booking = conn.execute(
        "SELECT b.id, b.citizen_id, b.dose_number, b.status, "
        "       s.date, s.vaccine "
        "FROM bookings b JOIN slots s ON s.id = b.slot_id WHERE b.id = ?",
        (booking_id,)).fetchone()
    if booking is None:
        raise NotFoundError(f"Booking {booking_id} not found.")
    if booking["status"] != "BOOKED":
        raise RuleViolation(
            f"Booking {booking_id} is {booking['status']}; "
            "a dose can only be recorded once, for an active booking.")
    with conn:
        cur = conn.execute(
            "INSERT INTO doses (citizen_id, booking_id, dose_number, "
            "                   vaccine, batch, date_given) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (booking["citizen_id"], booking_id, booking["dose_number"],
             booking["vaccine"], batch, booking["date"]))
        conn.execute(
            "UPDATE bookings SET status = 'COMPLETED' WHERE id = ?",
            (booking_id,))
    return cur.lastrowid
