"""Tests for the shared web helpers."""
from datetime import date

from vaccination import web


def test_require_role_blocks_and_allows(app):
    @app.route("/_only-testers")
    @web.require_role("tester")
    def only_testers():
        return "secret"

    client = app.test_client()
    html = client.get("/_only-testers", follow_redirects=True)
    assert "Please log in first" in html.get_data(as_text=True)
    with client.session_transaction() as sess:
        sess["role"] = "tester"
    assert client.get("/_only-testers").get_data(as_text=True) == "secret"


def test_today_uses_fixed_date_or_real_date(app):
    with app.app_context():
        assert web._today() == date(2026, 11, 2)  # pylint: disable=W0212
        app.config["TODAY"] = None
        assert web._today() == date.today()  # pylint: disable=W0212
