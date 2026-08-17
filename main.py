import re
import sqlite3
import string
'''
The random libary uses the Mersenne Twister pseudo-random number generator and therefore it is not cryptographically secure
If security was a concern, we would need a more secure random number generator such as the one found in the secrets library
'''
import random
from flask import Flask, request, redirect, jsonify, g, abort

DB_PATH = "urls.db" # Path to our sqlite database file

CODE_LENGTH = 6 # Length of the code after the last slash

SUCCESS_CODE = 200
REDIRECT = 302
BAD_REQUEST = 400
NOT_FOUND = 404
CODE_ALREADY_TAKEN = 409

PORT = 5000

CODE_ALPHABET = string.ascii_letters + string.digits # String of all characters that can be used in the code

app = Flask(__name__) # Create a Flask app

'''
This function will return a database connection object
If there is no database yet, it will create one

About thread safety:
If this connection is shared by multiple threads, ProgrammingError will be raised
g stores the connection for the duration of a single http request
Every request handles its own connection, which is automatically closed because of @app.teardown_appcontext
'''
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


'''
Function to close the database connection
'''
@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


'''
Initialize the database with a "urls" table
This table will store the original URL and the the code that will be used to access it

Note: This function will need to be called manually, because it is not called by the app
'''
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

# Regular expression to check if the URL is valid
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

'''
Function to normalize the URL (strip white space, add http:// if missing and make sure it is a valid URL)
'''
def normalize_url(url: str) -> str:
    url = url.strip()
    if not URL_RE.match(url):
        url = "http://" + url
    return url


'''
Generate a random code of the given length
The characters used in the code are all from CODE_ALPHABET string
'''
def generate_code(db, length: int = CODE_LENGTH) -> str:
    while True:
        code = "".join(random.choices(CODE_ALPHABET, k=length))
        exists = db.execute(
            "SELECT 1 FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if not exists:
            return code


'''
HTML structure of the home page

The javascript code at the bottom only declares an asynchronous function to shorten the URL
This function is attached to the "Shorten" button

It will grab the URL from the #url input field and send it to the /api/shorten route

Json format of the response from the API:
{
    "short_url": string,
    "code": string,
    "original_url": string
}

The result of the shortening is displayed in the #result div

When res.ok is false, it parses the data.error field and displays it in the #result div instead of a link
'''
INDEX_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>URL Shortener</title>
    <style>
        body { font-family: sans-serif; max-width: 480px; margin: 60px auto; }
        input[type=text] { width: 100%; padding: 8px; margin-bottom: 10px; box-sizing: border-box; }
        button { padding: 8px 16px; }
        #result { margin-top: 20px; word-break: break-all; }
    </style>
</head>
<body>
    <h2>URL Shortener</h2>
    <input type="text" id="url" placeholder="https://example.com/some/long/url">
    <input type="text" id="custom_code" placeholder="Custom code (optional)">
    <button onclick="shorten()">Shorten</button>
    <div id="result"></div>

    <script>
        async function shorten() {
            const url = document.getElementById('url').value;
            const customCode = document.getElementById('custom_code').value.trim();
            
            const payload = { url };
            if (customCode) {
                payload.code = customCode;
            }

            const res = await fetch('/api/shorten', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
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

'''
Root route of the app
Return the home page specified above
'''
@app.route("/")
def index():
    return INDEX_HTML

'''
Api route to shorten a URL

custom_code is an optional parameter that can be used to specify a custom code for the URL

Status codes:
200 - Success
400 - Bad request (missing url or invalid custom code)
409 - Code already taken
'''
@app.route("/api/shorten", methods=["POST"])
def api_shorten():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not url or not url.strip():
        return jsonify({"error": "Missing 'url' field"}), BAD_REQUEST

    url = normalize_url(url)
    db = get_db()

    custom_code = data.get("code")
    if custom_code:
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", custom_code):
            return jsonify({"error": "Invalid custom code"}), BAD_REQUEST
        exists = db.execute(
            "SELECT 1 FROM urls WHERE code = ?", (custom_code,)
        ).fetchone()
        if exists:
            return jsonify({"error": "Code already taken"}), CODE_ALREADY_TAKEN
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


'''
Route to redirect to the original URL, given the code

Note: This function will perform a write operation on the database. More specifically, it will increment the clicks counter

Status codes:
302 - Redirect to the original URL
404 - Code not found - returns the default 404 error page
'''
@app.route("/<code>")
def redirect_to_url(code):
    db = get_db()
    row = db.execute(
        "SELECT original_url FROM urls WHERE code = ?", (code,)
    ).fetchone()
    if row is None:
        abort(NOT_FOUND)
    db.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
    db.commit()
    return redirect(row["original_url"], code=REDIRECT)


'''
Api route to get the stats of a code

The statistics include the original URL, the number of clicks and the code itself
If the code is not found, a 404 error is returned

Status codes:
200 - Success
404 - Code not found

Json format of the response:
{
    "code": string,
    "original_url": string,
    "clicks": int
}
'''
@app.route("/api/stats/<code>")
def api_stats(code):
    db = get_db()
    row = db.execute(
        "SELECT original_url, clicks FROM urls WHERE code = ?", (code,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "Code not found"}), NOT_FOUND
    return jsonify(
        {"code": code, "original_url": row["original_url"], "clicks": row["clicks"]}
    )


if __name__ == "__main__":
    # Initialize the database and start the app
    init_db()
    app.run(debug=True, port=PORT)