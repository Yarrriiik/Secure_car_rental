import hashlib
import secrets
import time

P = 170141183460469231731687303715884105727
G = 5
_dh_sessions = {}


def create_dh_session(ttl_seconds: int = 300):
    private_key = secrets.randbelow(P - 2) + 2
    public_key = pow(G, private_key, P)
    session_id = secrets.token_urlsafe(16)

    _dh_sessions[session_id] = {
        "private_key": private_key,
        "created_at": time.time(),
        "ttl": ttl_seconds,
    }
    return session_id, P, G, public_key


def derive_shared_key(session_id: str, client_public_key: int):
    session = _dh_sessions.get(session_id)
    if not session:
        return None

    if time.time() - session["created_at"] > session["ttl"]:
        _dh_sessions.pop(session_id, None)
        return None

    shared_secret = pow(client_public_key, session["private_key"], P)
    _dh_sessions.pop(session_id, None)

    shared_bytes = shared_secret.to_bytes((shared_secret.bit_length() + 7) // 8, "big")
    return hashlib.sha256(shared_bytes).digest()
