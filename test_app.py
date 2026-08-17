import pytest
import main as main_module
from main import app, init_db

@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_urls.db")
    main_module.DB_PATH = test_db
    init_db()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    # Root page should return the html content and status code 200
    response = client.get("/")
    assert response.status_code == 200
    assert b"URL Shortener" in response.data

def test_shorten_url(client):
    # Test shortening a valid url, I'll use a random long url for the test
    payload = {"url": "https://google.com/"}
    response = client.post("/api/shorten", json=payload)

    # We should get back a json with the code and original url
    assert response.status_code == 200
    data = response.json
    assert "short_url" in data # short_url is the full shortened url including the code
    assert "code" in data # code is only the 6 character code at the end
    assert len(data["code"]) == 6 # code should be 6 characters
    assert data["original_url"] == payload["url"] # original url should be the same as the one we sent


def test_shorten_url_adds_missing_scheme(client):
    # Test that the normalization function adds the missing http/https scheme
    payload = {"url": "github.com"}
    response = client.post("/api/shorten", json=payload)

    assert response.status_code == 200
    data = response.json
    assert data["original_url"] == "http://github.com"

def test_shorten_url_custom_code(client):
    # Test adding a custom code rather than generating the 6 character one
    payload = {"url": "https://python.org", "code": "py-docs"}
    response = client.post("/api/shorten", json=payload)

    assert response.status_code == 200
    data = response.json
    assert data["code"] == "py-docs"

def test_shorten_url_duplicate_custom_code(client):
    # We should get a 409 error if the code is already taken
    payload = {"url": "https://python.org", "code": "py-docs"}
    client.post("/api/shorten", json=payload) # First add

    response = client.post("/api/shorten", json=payload) # Then try to add again

    assert response.status_code == 409
    assert response.get_json()["error"] == "Code already taken"

def test_redirect_and_click_counter(client):
    # When we visit a page, the click counter should be incremented
    client.post("/api/shorten", json={"url": "https://pypi.org", "code": "pypi"})

    redirect_res = client.get("/pypi")
    assert redirect_res.status_code == 302 # Redirect status code
    assert redirect_res.headers["Location"] == "https://pypi.org"

    stats_res = client.get("/api/stats/pypi")
    assert stats_res.status_code == 200
    assert stats_res.json["clicks"] == 1


def stats_not_found(client):
    # When we try to access stats of a non-existent code, we should get a 404 error
    response = client.get("/api/stats/non-existent")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Code not found"