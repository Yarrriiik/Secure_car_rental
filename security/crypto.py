import base64
import hashlib
import os


def generate_salt(length: int = 16) -> str:
    return base64.b64encode(os.urandom(length)).decode("utf-8")


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
