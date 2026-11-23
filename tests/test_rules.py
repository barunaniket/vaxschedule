"""Unit tests for rules.py (UT-R1 to UT-R9)."""
from datetime import date

import pytest

from vaccination import rules
from vaccination.rules import RuleViolation, ValidationError


def test_age_on_birthday_boundary():  # UT-R1
    dob = date(2000, 6, 15)
    assert rules.age_on(dob, date(2026, 6, 14)) == 25
    assert rules.age_on(dob, date(2026, 6, 15)) == 26


@pytest.mark.parametrize("mobile", ["9876543210", "6000000000"])
def test_valid_mobiles(mobile):  # UT-R2
    rules.validate_mobile(mobile)


@pytest.mark.parametrize(
    "mobile", ["", None, "12345", "5876543210", "98765432101", "98765abcde"])
def test_invalid_mobiles(mobile):  # UT-R3
    with pytest.raises(ValidationError, match="10 digits"):
        rules.validate_mobile(mobile)


@pytest.mark.parametrize("value", ["17/05/1990", None, "2026-02-30"])
def test_parse_date_rejects_bad_values(value):  # UT-R4
    with pytest.raises(ValidationError):
        rules.parse_date(value)


def test_parse_date_accepts_iso_and_date_objects():
    assert rules.parse_date("2026-11-02") == date(2026, 11, 2)
    assert rules.parse_date(date(2026, 1, 1)) == date(2026, 1, 1)


def test_unknown_vaccine():  # UT-R5
    with pytest.raises(ValidationError, match="Unknown vaccine"):
        rules.validate_vaccine("Sputnik")


def test_next_dose_date():  # UT-R6
    assert rules.next_dose_date("Covaxin", "2026-01-01") == date(2026, 1, 29)
    assert rules.next_dose_date("Covishield", "2026-01-01") == \
        date(2026, 3, 26)


def test_dose_two_one_day_early_is_refused():  # UT-R7
    with pytest.raises(RuleViolation,
                       match="Dose not allowed before 2026-01-29"):
        rules.check_dose_interval("Covaxin", "2026-01-01", "2026-01-28")


def test_dose_two_on_the_allowed_day():  # UT-R8
    earliest = rules.check_dose_interval(
        "Covaxin", "2026-01-01", "2026-01-29")
    assert earliest == date(2026, 1, 29)


def test_is_fully_vaccinated():  # UT-R9
    assert rules.is_fully_vaccinated("Covaxin", 1) is False
    assert rules.is_fully_vaccinated("Covaxin", 2) is True
