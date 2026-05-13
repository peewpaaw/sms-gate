import hashlib


def hash_api_key(api_key: str) -> str:
    """Hash API key using SHA-256."""
    return hashlib.sha256(api_key.encode()).hexdigest()
