# app/encryption.py
import os
from cryptography.fernet import Fernet

# 1. Load the encryption key from the environment
key_str = os.getenv("DATA_ENCRYPTION_KEY")
if not key_str:
    raise ValueError("DATA_ENCRYPTION_KEY is not set! App cannot start.")

key = key_str.encode()  # Convert to bytes
cipher_suite = Fernet(key)


def encrypt_data(plain_text: str) -> str:
    """
    Encrypts a string and returns it as a string.
    """
    if not plain_text:
        return ""

    encrypted_bytes = cipher_suite.encrypt(plain_text.encode())
    return encrypted_bytes.decode()  # Store as a plain string


def decrypt_data(encrypted_text: str) -> str:
    """
    Decrypts a string and returns it.
    Returns an error message if decryption fails.
    """
    if not encrypted_text:
        return ""

    try:
        decrypted_bytes = cipher_suite.decrypt(encrypted_text.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        print(f"Error decrypting data: {e}")
        return "[This note could not be decrypted. Key may have changed.]"
