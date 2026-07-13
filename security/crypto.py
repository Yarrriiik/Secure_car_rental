import hashlib
import hmac

import bcrypt


def hash_password(password: str) -> str:
    """Return a bcrypt password hash suitable for persistent storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), encoded_hash.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def verify_legacy_password(password: str, salt: str | None, encoded_hash: str) -> bool:
    """Verify the pre-bcrypt salted SHA-256 format during migration only."""
    if not salt:
        return False
    candidate = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, encoded_hash)
