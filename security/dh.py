# security/dh.py
import secrets
import hashlib
import time

# Простые параметры для DH (для учебной задачи, не для продакшена)
P = 170141183460469231731687303715884105727  # 2^127 - 1, простое число
G = 5

# Простое in-memory-хранилище состояний DH-сессий
_dh_sessions = {}


def create_dh_session(ttl_seconds: int = 300):
    """
    Создаёт новую DH-сессию:
    - генерит приватный ключ сервера a
    - считает публичный ключ A = g^a mod p
    - возвращает dh_id + (p, g, A)
    """
    priv = secrets.randbelow(P - 2) + 2  # 2..P-1
    pub = pow(G, priv, P)

    dh_id = secrets.token_urlsafe(16)
    _dh_sessions[dh_id] = {
        "priv": priv,
        "created_at": time.time(),
        "ttl": ttl_seconds,
    }
    return dh_id, P, G, pub


def derive_shared_key(dh_id: str, client_pub: int):
    """
    По сохранённому приватному ключу и публичному ключу клиента
    считает общий секрет и из него делает 32-байтный ключ (SHA-256).
    """
    sess = _dh_sessions.get(dh_id)
    if not sess:
        return None

    # истекла ли сессия
    if time.time() - sess["created_at"] > sess["ttl"]:
        _dh_sessions.pop(dh_id, None)
        return None

    priv = sess["priv"]
    # общий секрет K = B^a mod p
    shared = pow(client_pub, priv, P)

    # DH-сессию можно выкинуть (одноразовая)
    _dh_sessions.pop(dh_id, None)

    # превращаем число в байты и хешируем
    shared_bytes = shared.to_bytes((shared.bit_length() + 7) // 8, "big")
    key = hashlib.sha256(shared_bytes).digest()  # 32 байта
    return key
