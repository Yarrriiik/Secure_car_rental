# security/symmetric.py
import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore
from cryptography.hazmat.primitives import padding  # type: ignore
from cryptography.hazmat.backends import default_backend  # type: ignore


def decrypt_password_aes_cbc(key: bytes, iv_b64: str, ciphertext_b64: str) -> str:
    """
    Расшифровывает пароль, зашифрованный AES-CBC с PKCS7-паддингом.
    key: 16/24/32 байт (у нас 32 байта из SHA-256).
    iv_b64, ciphertext_b64: base64-строки.
    """
    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(ciphertext_b64)

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded) + unpadder.finalize()

    return data.decode("utf-8")
