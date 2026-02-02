import bcrypt

def hash_password(plain_text_password: str) -> str:
    hashed = bcrypt.hashpw(plain_text_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")

def verify_password(plain_text_password: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(
        plain_text_password.encode("utf-8"),
        stored_hash.encode("utf-8"),
    )
