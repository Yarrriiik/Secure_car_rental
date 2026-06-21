import base64
import hashlib
import os
import secrets

import requests
from cryptography.hazmat.backends import default_backend  # type: ignore
from cryptography.hazmat.primitives import padding  # type: ignore
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
USERNAME = os.getenv("TEST_USERNAME", "testuser")
PASSWORD = os.getenv("TEST_PASSWORD", "testpass")


def aes_encrypt(key: bytes, plaintext: str):
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    return (
        base64.b64encode(iv).decode("utf-8"),
        base64.b64encode(ciphertext).decode("utf-8"),
    )


def main() -> None:
    response = requests.get(f"{BASE_URL}/api/dh-init", timeout=10)
    response.raise_for_status()
    data = response.json()

    dh_id = data["dh_id"]
    prime = int(data["p"])
    generator = int(data["g"])
    server_public = int(data["server_pub"])

    private_key = secrets.randbelow(prime - 2) + 2
    client_public = pow(generator, private_key, prime)

    shared_secret = pow(server_public, private_key, prime)
    shared_bytes = shared_secret.to_bytes((shared_secret.bit_length() + 7) // 8, "big")
    aes_key = hashlib.sha256(shared_bytes).digest()
    iv_b64, ciphertext_b64 = aes_encrypt(aes_key, PASSWORD)

    payload = {
        "username": USERNAME,
        "dh_id": dh_id,
        "client_pub": str(client_public),
        "iv": iv_b64,
        "ciphertext": ciphertext_b64,
    }

    login_response = requests.post(f"{BASE_URL}/api/login_secure", json=payload, timeout=10)
    print("login_secure:", login_response.status_code, login_response.text)


if __name__ == "__main__":
    main()
