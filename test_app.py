import pytest
import main as main_module
from main import app, init_db
from main import CODE_LENGTH
from main import SUCCESS_CODE, REDIRECT, NOT_FOUND, CODE_ALREADY_TAKEN


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
    assert response.status_code == SUCCESS_CODE
    assert b"URL Shortener" in response.data

def test_shorten_url(client):
    # Test shortening a valid url
    payload = {"url": "https://google.com/"}
    response = client.post("/api/shorten", json=payload)

    # We should get back a json with the code and original url
    assert response.status_code == SUCCESS_CODE
    data = response.json
    assert "short_url" in data # short_url is the full shortened url including the code
    assert "code" in data # code is only the 6 character code at the end
    assert len(data["code"]) == CODE_LENGTH # code should be 6 characters
    assert data["original_url"] == payload["url"] # original url should be the same as the one we sent


def test_shorten_url_adds_missing_scheme(client):
    # Test that the normalization function adds the missing http/https scheme
    payload = {"url": "github.com"}
    response = client.post("/api/shorten", json=payload)

    assert response.status_code == SUCCESS_CODE
    data = response.json
    assert data["original_url"] == "http://github.com"

def test_shorten_url_custom_code(client):
    # Test adding a custom code rather than generating the 6 character random one
    payload = {"url": "https://python.org", "code": "py-docs"}
    response = client.post("/api/shorten", json=payload)

    assert response.status_code == SUCCESS_CODE
    data = response.json
    assert data["code"] == "py-docs"

def test_shorten_url_duplicate_custom_code(client):
    # We should get a 409 error if the code is already taken
    payload = {"url": "https://python.org", "code": "py-docs"}
    client.post("/api/shorten", json=payload) # First add

    response = client.post("/api/shorten", json=payload) # Then try to add again

    assert response.status_code == CODE_ALREADY_TAKEN
    assert response.get_json()["error"] == "Code already taken"

def test_redirect_and_click_counter(client):
    # When we visit a page, the click counter should be incremented
    client.post("/api/shorten", json={"url": "https://pypi.org", "code": "pypi"})

    EXPECTED_COUNT = 1

    redirect_res = client.get("/pypi")
    assert redirect_res.status_code == REDIRECT # Redirect status code
    assert redirect_res.headers["Location"] == "https://pypi.org"

    stats_res = client.get("/api/stats/pypi")
    assert stats_res.status_code == SUCCESS_CODE
    assert stats_res.json["clicks"] == EXPECTED_COUNT


def stats_not_found(client):
    # When we try to access stats of a non-existent code, we should get a 404 error
    response = client.get("/api/stats/non-existent")

    assert response.status_code == NOT_FOUND
    assert response.get_json()["error"] == "Code not found"