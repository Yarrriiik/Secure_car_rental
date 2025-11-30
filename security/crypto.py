# security/crypto.py
import os
import hashlib
import base64


def generate_salt(length: int = 16) -> str:
    return base64.b64encode(os.urandom(length)).decode("utf-8")


def hash_password(password: str, salt: str) -> str:
    data = (salt + password).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
