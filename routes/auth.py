# routes/auth.py
from flask import Blueprint, request, jsonify, make_response

from db import get_connection
from security.crypto import generate_salt, hash_password
from security.session import create_session
from security.auth_utils import require_role, delete_session
from security.dh import create_dh_session, derive_shared_key
from security.symmetric import decrypt_password_aes_cbc

auth_bp = Blueprint("auth", __name__)

def _perform_login(username: str, password: str):
    """
    Общая логика логина:
    - находит пользователя
    - проверяет хеш пароля
    - создаёт сессию и куку
    """
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

    ip = request.remote_addr or ""
    ua = request.headers.get("User-Agent", "")

    token = create_session(user["id"], ip, ua)

    resp = make_response(jsonify({"status": "ok"}))
    resp.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="Lax",
    )
    return resp, 200


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
        # Проверим, что такого логина ещё нет
        cur.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,),
        )
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

        # роль USER по умолчанию
        cur.execute("SELECT id FROM roles WHERE name = 'USER'")
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO roles (name) VALUES ('USER') RETURNING id")
            row = cur.fetchone()
        role_id = row["id"]
        cur.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
            (user_id, role_id),
        )

        conn.commit()
        return jsonify({"status": "ok", "user_id": user_id}), 201
    except Exception:
        conn.rollback()
        # Во внешнем API не светим текст SQL-ошибки
        return jsonify({"error": "internal error"}), 500
    finally:
        cur.close()
        conn.close()



@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    return _perform_login(username, password)



@auth_bp.route("/api/login_secure", methods=["POST"])
def login_secure():
    data = request.get_json() or {}
    username = data.get("username")
    dh_id = data.get("dh_id")
    client_pub_str = data.get("client_pub")
    iv_b64 = data.get("iv")
    ciphertext_b64 = data.get("ciphertext")

    # Базовые проверки
    if not username or not dh_id or not client_pub_str or not iv_b64 or not ciphertext_b64:
        return jsonify({"error": "username, dh_id, client_pub, iv, ciphertext required"}), 400

    try:
        client_pub = int(client_pub_str)
    except ValueError:
        return jsonify({"error": "invalid client_pub"}), 400

    # Восстанавливаем общий секретный ключ по DH
    key = derive_shared_key(dh_id, client_pub)
    if key is None:
        return jsonify({"error": "invalid or expired dh session"}), 400

    # Расшифровываем пароль
    try:
        password = decrypt_password_aes_cbc(key, iv_b64, ciphertext_b64)
    except Exception:
        return jsonify({"error": "invalid encrypted payload"}), 400

    # Дальше используем ту же логику, что и в обычном /api/login
    return _perform_login(username, password)



@auth_bp.route("/api/me", methods=["GET"])
@require_role("USER", "MANAGER", "ADMIN")
def me(current_user):
    return jsonify({
        "id": current_user["id"],
        "username": current_user["username"]
    }), 200

@auth_bp.route("/api/dh-init", methods=["GET"])
def dh_init():
    dh_id, p, g, server_pub = create_dh_session()
    return jsonify({
        "dh_id": dh_id,
        "p": str(p),
        "g": str(g),
        "server_pub": str(server_pub),
    }), 200

@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    token = request.cookies.get("session_token")
    if token:
        delete_session(token)  # у тебя уже должна быть функция удаления сессии
    resp = make_response(jsonify({"status": "ok"}))
    resp.delete_cookie("session_token")  # скажем браузеру забыть куку [web:292][web:294]
    return resp, 200
