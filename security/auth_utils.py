from datetime import datetime
from functools import wraps

from flask import jsonify, request

from db import get_connection
from security.session import token_digest


def get_current_user():
    token = request.cookies.get("session_token")
    if not token:
        return None

    ip_address = request.remote_addr or ""
    user_agent = request.headers.get("User-Agent", "")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT s.user_id, s.ip_address, s.user_agent, s.expires_at, u.username
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = %s
            """,
            (token_digest(token),),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if row is None:
        return None
    if row["expires_at"] < datetime.utcnow():
        return None
    if row["ip_address"] != ip_address or row["user_agent"] != user_agent:
        return None

    return {"id": row["user_id"], "username": row["username"]}


def get_user_roles(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = %s
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return {row["name"] for row in rows}


def require_role(*roles):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if user is None:
                return jsonify({"error": "unauthorized"}), 401

            user_roles = get_user_roles(user["id"])
            if not any(role in user_roles for role in roles):
                return jsonify({"error": "forbidden"}), 403

            return function(*args, current_user=user, **kwargs)

        return wrapper

    return decorator


def delete_session(token: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM sessions WHERE token = %s", (token_digest(token),))
        conn.commit()
    finally:
        cur.close()
        conn.close()
