"""Password Hashing Utility.

Provides bcrypt-based password hashing and verification.
"""

import bcrypt

if not hasattr(bcrypt, "__about__"):
    class About:
        __version__ = bcrypt.__version__
    bcrypt.__about__ = About

# Passlib bug workaround for python 3.12+ and bcrypt 4.1+
_orig_hashpw = bcrypt.hashpw
def _patched_hashpw(password, salt):
    return _orig_hashpw(password[:72], salt)
bcrypt.hashpw = _patched_hashpw

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)
