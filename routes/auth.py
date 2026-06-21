import os

from flask import Blueprint, jsonify, make_response, request

from db import get_connection
from security.auth_utils import delete_session, require_role
from security.crypto import generate_salt, hash_password
from security.dh import create_dh_session, derive_shared_key
from security.session import create_session
from security.symmetric import decrypt_password_aes_cbc

auth_bp = Blueprint("auth", __name__)
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"


def _build_login_response(user_id: int):
    ip_address = request.remote_addr or ""
    user_agent = request.headers.get("User-Agent", "")
    token = create_session(user_id, ip_address, user_agent)

    response = make_response(jsonify({"status": "ok"}))
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="Lax",
        secure=SESSION_COOKIE_SECURE,
    )
    return response, 200


def _perform_login(username: str, password: str):
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, password_hash, salt FROM users WHERE username = %s",
            (username,),
        )
        user = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if user is None:
        return jsonify({"error": "invalid credentials"}), 401

    expected_hash = hash_password(password, user["salt"])
    if expected_hash != user["password_hash"]:
        return jsonify({"error": "invalid credentials"}), 401

    return _build_login_response(user["id"])


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone() is not None:
            return jsonify({"error": "username already exists"}), 400

        salt = generate_salt()
        password_hash = hash_password(password, salt)

        cur.execute(
            """
            INSERT INTO users (username, password_hash, salt)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (username, password_hash, salt),
        )
        user_id = cur.fetchone()["id"]

        cur.execute("SELECT id FROM roles WHERE name = 'USER'")
        role = cur.fetchone()
        if role is None:
            cur.execute("INSERT INTO roles (name) VALUES ('USER') RETURNING id")
            role = cur.fetchone()

        cur.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
            (user_id, role["id"]),
        )
        conn.commit()
        return jsonify({"status": "ok", "user_id": user_id}), 201
    except Exception:
        conn.rollback()
        return jsonify({"error": "internal error"}), 500
    finally:
        cur.close()
        conn.close()


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    return _perform_login(data.get("username"), data.get("password"))


@auth_bp.route("/api/login_secure", methods=["POST"])
def login_secure():
    data = request.get_json() or {}
    username = data.get("username")
    dh_id = data.get("dh_id")
    client_pub_raw = data.get("client_pub")
    iv_b64 = data.get("iv")
    ciphertext_b64 = data.get("ciphertext")

    if not username or not dh_id or not client_pub_raw or not iv_b64 or not ciphertext_b64:
        return jsonify({"error": "username, dh_id, client_pub, iv, ciphertext required"}), 400

    try:
        client_pub = int(client_pub_raw)
    except ValueError:
        return jsonify({"error": "invalid client_pub"}), 400

    key = derive_shared_key(dh_id, client_pub)
    if key is None:
        return jsonify({"error": "invalid or expired dh session"}), 400

    try:
        password = decrypt_password_aes_cbc(key, iv_b64, ciphertext_b64)
    except Exception:
        return jsonify({"error": "invalid encrypted payload"}), 400

    return _perform_login(username, password)


@auth_bp.route("/api/me", methods=["GET"])
@require_role("USER", "MANAGER", "ADMIN")
def me(current_user):
    return jsonify({"id": current_user["id"], "username": current_user["username"]}), 200


@auth_bp.route("/api/dh-init", methods=["GET"])
def dh_init():
    dh_id, prime, generator, server_public = create_dh_session()
    return jsonify(
        {
            "dh_id": dh_id,
            "p": str(prime),
            "g": str(generator),
            "server_pub": str(server_public),
        }
    ), 200


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    token = request.cookies.get("session_token")
    if token:
        delete_session(token)

    response = make_response(jsonify({"status": "ok"}))
    response.delete_cookie("session_token", samesite="Lax", secure=SESSION_COOKIE_SECURE)
    return response, 200
