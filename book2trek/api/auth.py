"""
JWT auth for the REST API.

The server-rendered app uses Flask-Login sessions; the voice agent (and any
programmatic client) can't carry a cookie, so the /api layer authenticates with
a stateless JWT bearer token. Role is embedded in the token so endpoints can do
RBAC without a DB hit.
"""
from __future__ import annotations

import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import g, jsonify, request

from .. import config as C


def create_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=C.JWT_TTL_MIN),
    }
    return jwt.encode(payload, C.JWT_SECRET, algorithm=C.JWT_ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, C.JWT_SECRET, algorithms=[C.JWT_ALGO])


def jwt_required(*roles: str):
    """Require a valid bearer token; optionally restrict to given roles."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify(error="missing bearer token"), 401
            try:
                claims = decode_token(auth[7:])
            except jwt.ExpiredSignatureError:
                return jsonify(error="token expired"), 401
            except jwt.InvalidTokenError:
                return jsonify(error="invalid token"), 401
            if roles and claims.get("role") not in roles:
                return jsonify(error="forbidden for this role"), 403
            g.user_id = int(claims["sub"])
            g.role = claims.get("role")
            return fn(*args, **kwargs)
        return wrapped
    return decorator
