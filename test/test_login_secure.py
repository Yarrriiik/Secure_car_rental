import base64
import hashlib
import os
import secrets

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore
from cryptography.hazmat.primitives import padding  # type: ignore
from cryptography.hazmat.backends import default_backend  # type: ignore

BASE_URL = "http://127.0.0.1:5000"
USERNAME = "testuser"
PASSWORD = "testpass"  # реальный пароль пользователя в БД


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


def main():
    # 1. Инициализация DH на сервере
    r = requests.get(f"{BASE_URL}/api/dh-init")
    print("dh-init:", r.status_code, r.text)
    r.raise_for_status()
    data = r.json()

    dh_id = data["dh_id"]
    p = int(data["p"])
    g = int(data["g"])
    server_pub = int(data["server_pub"])

    # 2. Клиент генерит свой секрет b и публичный ключ B = g^b mod p
    b = secrets.randbelow(p - 2) + 2
    client_pub = pow(g, b, p)

    # 3. Общий секрет K = A^b mod p
    shared = pow(server_pub, b, p)
    shared_bytes = shared.to_bytes((shared.bit_length() + 7) // 8, "big")
    key = hashlib.sha256(shared_bytes).digest()  # 32-байтный AES-ключ

    # 4. Шифруем пароль AES-CBC
    iv_b64, ciphertext_b64 = aes_encrypt(key, PASSWORD)

    payload = {
        "username": USERNAME,
        "dh_id": dh_id,
        "client_pub": str(client_pub),
        "iv": iv_b64,
        "ciphertext": ciphertext_b64,
    }

    # 5. Логин через /api/login_secure
    r2 = requests.post(f"{BASE_URL}/api/login_secure", json=payload)
    print("login_secure:", r2.status_code, r2.text)


if __name__ == "__main__":
    main()
