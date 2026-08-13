#!/usr/bin/env python3
import re
import sqlite3
import string
import random
from flask import Flask, request, redirect, jsonify, g, abort

DB_PATH = "urls.db"
CODE_LENGTH = 6
CODE_ALPHABET = string.ascii_letters + string.digits

app = Flask(__name__)
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            code TEXT PRIMARY KEY,
            original_url TEXT NOT NULL,
            clicks INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def normalize_url(url: str) -> str:
    url = url.strip()
    if not URL_RE.match(url):
        url = "http://" + url
    return url


def generate_code(db, length: int = CODE_LENGTH) -> str:
    while True:
        code = "".join(random.choices(CODE_ALPHABET, k=length))
        exists = db.execute(
            "SELECT 1 FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if not exists:
            return code


INDEX_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>URL Shortener</title>
    <style>
        body { font-family: sans-serif; max-width: 480px; margin: 60px auto; }
        input[type=text] { width: 100%; padding: 8px; box-sizing: border-box; }
        button { margin-top: 10px; padding: 8px 16px; }
        #result { margin-top: 20px; word-break: break-all; }
    </style>
</head>
<body>
    <h2>URL Shortener</h2>
    <input type="text" id="url" placeholder="https://example.com/some/long/url">
    <button onclick="shorten()">Shorten</button>
    <div id="result"></div>

    <script>
        async function shorten() {
            const url = document.getElementById('url').value;
            const res = await fetch('/api/shorten', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            });
            const data = await res.json();
            const result = document.getElementById('result');
            if (res.ok) {
                result.innerHTML = 'Short URL: <a href="' + data.short_url +
                    '" target="_blank">' + data.short_url + '</a>';
            } else {
                result.innerHTML = 'Error: ' + data.error;
            }
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return INDEX_HTML


@app.route("/api/shorten", methods=["POST"])
def api_shorten():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not url or not url.strip():
        return jsonify({"error": "Missing 'url' field"}), 400

    url = normalize_url(url)
    db = get_db()

    custom_code = data.get("code")
    if custom_code:
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", custom_code):
            return jsonify({"error": "Invalid custom code"}), 400
        exists = db.execute(
            "SELECT 1 FROM urls WHERE code = ?", (custom_code,)
        ).fetchone()
        if exists:
            return jsonify({"error": "Code already taken"}), 409
        code = custom_code
    else:
        code = generate_code(db)

    db.execute(
        "INSERT INTO urls (code, original_url, clicks) VALUES (?, ?, 0)",
        (code, url),
    )
    db.commit()

    short_url = request.host_url.rstrip("/") + "/" + code
    return jsonify({"short_url": short_url, "code": code, "original_url": url})


@app.route("/<code>")
def redirect_to_url(code):
    db = get_db()
    row = db.execute(
        "SELECT original_url FROM urls WHERE code = ?", (code,)
    ).fetchone()
    if row is None:
        abort(404)
    db.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
    db.commit()
    return redirect(row["original_url"], code=302)


@app.route("/api/stats/<code>")
def api_stats(code):
    db = get_db()
    row = db.execute(
        "SELECT original_url, clicks FROM urls WHERE code = ?", (code,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "Code not found"}), 404
    return jsonify(
        {"code": code, "original_url": row["original_url"], "clicks": row["clicks"]}
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
