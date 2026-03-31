from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
