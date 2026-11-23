"""Business rules and exceptions. Pure functions, no database access."""
import re
from datetime import date, datetime, timedelta

VACCINES = {
    "Covishield": {"doses": 2, "interval_days": 84},
    "Covaxin": {"doses": 2, "interval_days": 28},
}
MIN_AGE = 18

_MOBILE_RE = re.compile(r"[6-9]\d{9}")


class VaccinationError(Exception):
    """Base class for every error the app shows to a user."""


class ValidationError(VaccinationError):
    """Bad input."""


class NotFoundError(VaccinationError):
    """A record that should exist does not."""


class RuleViolation(VaccinationError):
    """A business rule was broken."""


def parse_date(value):
    """Parse an ISO ``YYYY-MM-DD`` string. ``date`` objects pass through."""
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"Invalid date {value!r}: use YYYY-MM-DD.") from exc


def age_on(dob, on_day):
    """Age in whole years on ``on_day``."""
    years = on_day.year - dob.year
    if (on_day.month, on_day.day) < (dob.month, dob.day):
        years -= 1
    return years


def validate_mobile(mobile):
    """A mobile number is 10 digits and starts with 6, 7, 8 or 9."""
    if not isinstance(mobile, str) or not _MOBILE_RE.fullmatch(mobile):
        raise ValidationError(
            "Mobile number must be 10 digits starting with 6-9.")


def validate_vaccine(vaccine):
    """Only the vaccines in ``VACCINES`` are allowed."""
    if vaccine not in VACCINES:
        raise ValidationError(f"Unknown vaccine: {vaccine!r}.")


def next_dose_date(vaccine, previous_dose_date):
    """Earliest date the next dose may be given."""
    validate_vaccine(vaccine)
    gap = timedelta(days=VACCINES[vaccine]["interval_days"])
    return parse_date(previous_dose_date) + gap


def check_dose_interval(vaccine, previous_dose_date, requested_date):
    """Raise ``RuleViolation`` if ``requested_date`` is too early.

    Returns the earliest allowed date.
    """
    earliest = next_dose_date(vaccine, previous_dose_date)
    if parse_date(requested_date) < earliest:
        raise RuleViolation(
            f"Dose not allowed before {earliest.isoformat()}.")
    return earliest


def is_fully_vaccinated(vaccine, doses_taken):
    """True once the citizen has every dose of their vaccine."""
    validate_vaccine(vaccine)
    return doses_taken >= VACCINES[vaccine]["doses"]
