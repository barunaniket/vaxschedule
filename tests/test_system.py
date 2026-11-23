"""System validation tests (ST-01 to ST-15) through the Flask test client."""


def page(response):
    return response.get_data(as_text=True)


def test_home_page(client):
    assert "Vaccination booking portal" in page(client.get("/"))
