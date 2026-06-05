import base64
from django.conf import settings

"""
This module provides database encryption and decryption utilities for chat messages.
It uses a lightweight, robust XOR-based symmetric encryption pattern.
XOR encryption is used here to secure message text in the SQLite database without
depending on heavy external compilation packages (like cryptography).
"""

def get_encrypt_key():
    """
    Derives a 32-byte encryption key from settings.SECRET_KEY.
    Ensures that the key is exactly 32 bytes by padding with 'x' or slicing.
    """
    key = getattr(settings, 'SECRET_KEY', 'default_secret_key_for_iia_management')
    if len(key) < 32:
        key = key.ljust(32, 'x')
    return key[:32].encode('utf-8')

def encrypt_data(plain_text):
    """
    Encrypts plain text using XOR encryption and returns a Base64 encoded string prefixed with 'enc::'.
    
    If encryption fails or input is empty, returns the original text to prevent crashes.
    """
    if not plain_text:
        return plain_text
    try:
        key = get_encrypt_key()
        plain_bytes = str(plain_text).encode('utf-8')
        encrypted_bytes = bytearray()
        
        # Perform XOR byte-by-byte with the repeating key pattern
        for i, byte in enumerate(plain_bytes):
            key_byte = key[i % len(key)]
            encrypted_bytes.append(byte ^ key_byte)
            
        # Prefix the Base64 output to identify it as encrypted in database queries
        return "enc::" + base64.b64encode(encrypted_bytes).decode('utf-8')
    except Exception:
        return plain_text

def decrypt_data(cipher_text):
    """
    Decrypts a Base64 XOR-encrypted string starting with the 'enc::' prefix.
    If the prefix is missing or decryption fails, returns the string as-is.
    """
    if not cipher_text or not str(cipher_text).startswith("enc::"):
        return cipher_text
    try:
        key = get_encrypt_key()
        # Decode Base64 payload (slicing out the 'enc::' prefix)
        cipher_bytes = base64.b64decode(cipher_text[5:].encode('utf-8'))
        decrypted_bytes = bytearray()
        
        # Reverse the XOR operation
        for i, byte in enumerate(cipher_bytes):
            key_byte = key[i % len(key)]
            decrypted_bytes.append(byte ^ key_byte)
            
        return decrypted_bytes.decode('utf-8')
    except Exception:
        return cipher_text
