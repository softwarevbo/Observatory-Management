import base64
from django.conf import settings

def get_encrypt_key():
    # Derive a 32-byte key from settings.SECRET_KEY
    key = getattr(settings, 'SECRET_KEY', 'default_secret_key_for_iia_management')
    if len(key) < 32:
        key = key.ljust(32, 'x')
    return key[:32].encode('utf-8')

def encrypt_data(plain_text):
    if not plain_text:
        return plain_text
    try:
        key = get_encrypt_key()
        # Simple, robust XOR encryption (does not depend on cryptography module)
        plain_bytes = str(plain_text).encode('utf-8')
        encrypted_bytes = bytearray()
        for i, byte in enumerate(plain_bytes):
            key_byte = key[i % len(key)]
            encrypted_bytes.append(byte ^ key_byte)
        return "enc::" + base64.b64encode(encrypted_bytes).decode('utf-8')
    except Exception:
        return plain_text

def decrypt_data(cipher_text):
    if not cipher_text or not str(cipher_text).startswith("enc::"):
        return cipher_text
    try:
        key = get_encrypt_key()
        cipher_bytes = base64.b64decode(cipher_text[5:].encode('utf-8'))
        decrypted_bytes = bytearray()
        for i, byte in enumerate(cipher_bytes):
            key_byte = key[i % len(key)]
            decrypted_bytes.append(byte ^ key_byte)
        return decrypted_bytes.decode('utf-8')
    except Exception:
        return cipher_text
