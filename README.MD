# Flask URL Shortener

A lightweight, dependency-free URL shortener built with Python, Flask, and SQLite. It provides a web interface for generating short links, supports custom aliases, tracks redirect click counts, and exposes a RESTful API.

---

## Features

- **Single-File Architecture**: Self-contained web app with embedded HTML UI and inline JavaScript.
- **Custom Short Codes**: Allows optional user-defined codes (`A-Z`, `a-z`, `0-9`, `_`, `-`, length 3–32).
- **Collision Resistance**: Auto-generates unique 6-character random alphanumeric codes.
- **URL Normalization**: Handles missing schemes (`http://`/`https://`) and whitespace trimming automatically.
- **Analytics**: Tracks hit/click counts for every shortened link.
- **REST API**: Standard JSON endpoints for shortening links and querying link statistics.

---

## Tech Stack

- **Language**: Python 3.13
- **Framework**: Flask
- **Database**: SQLite3 (embedded)

---

## Getting Started

### Prerequisites

Ensure Python 3.8+ is installed on your machine. Install Flask via `pip`:

```bash
pip install flask
```

Clone the repository:
```bash
git clone https://github.com/sami-turunen/url-shortener-flask
```

Install flask:
```bash
pip install flask
```

Start the app:
```bash
python main.py
```

Open your browser and navigate to http://127.0.0.1:5000/.