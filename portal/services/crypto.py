import base64, hashlib, os
from cryptography.fernet import Fernet
from django.conf import settings

def _fernet():
    key=os.getenv('PORTAL_FERNET_KEY','').strip()
    if key:
        return Fernet(key.encode())
    digest=hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

def encrypt(value):
    if not value: return ''
    return _fernet().encrypt(value.encode()).decode()

def decrypt(value):
    if not value: return ''
    try: return _fernet().decrypt(value.encode()).decode()
    except Exception: return ''
