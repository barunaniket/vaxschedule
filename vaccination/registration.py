"""FR-001: citizen registration and login."""
import re
import sqlite3
from datetime import date

from .rules import (MIN_AGE, NotFoundError, ValidationError, age_on,
                    parse_date, validate_mobile)

_ID_RE = re.compile(r"[A-Z0-9]{6,}")


def register_citizen(conn, name, dob, id_number, mobile, today=None):
    """Validate the details and store a new citizen. Returns the id."""
    today = today or date.today()
    name = (name or "").strip()
    id_number = (id_number or "").strip().upper()
    mobile = (mobile or "").strip()

    if len(name) < 2:
        raise ValidationError("Name must be at least 2 characters.")
    if not _ID_RE.fullmatch(id_number):
        raise ValidationError(
            "ID number must be at least 6 letters or digits.")
    validate_mobile(mobile)
    born = parse_date(dob)
    if born > today:
        raise ValidationError("Date of birth cannot be in the future.")
    if age_on(born, today) < MIN_AGE:
        raise ValidationError(
            f"You must be at least {MIN_AGE} years old to register.")

    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO citizens (name, dob, id_number, mobile) "
                "VALUES (?, ?, ?, ?)",
                (name, born.isoformat(), id_number, mobile))
    except sqlite3.IntegrityError as exc:
        raise ValidationError(
            "A citizen with this ID number is already registered.") from exc
    return cur.lastrowid


def get_citizen(conn, citizen_id):
    """Fetch one citizen or raise ``NotFoundError``."""
    row = conn.execute(
        "SELECT * FROM citizens WHERE id = ?", (citizen_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Citizen {citizen_id} not found.")
    return row


def find_by_login(conn, id_number, mobile):
    """Log in with ID number and mobile."""
    row = conn.execute(
        "SELECT * FROM citizens WHERE id_number = ? AND mobile = ?",
        ((id_number or "").strip().upper(), (mobile or "").strip()),
    ).fetchone()
    if row is None:
        raise NotFoundError(
            "No citizen found with that ID number and mobile.")
    return row
