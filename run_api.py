#!/usr/bin/env python
"""
Run the existing TrekTrack app WITH the /api layer attached.

    python seed.py        # once: create tables + seed admin
    python run_api.py      # serves the web app + REST API on :5000

The server-rendered site keeps working exactly as before; this just registers
the /api blueprint on the same app so the voice agent (and any client) can call
JWT-authenticated REST endpoints against the same database.
"""
from app import app          # the existing Flask app (routes, login, models)
from book2trek.api.blueprint import register

register(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
