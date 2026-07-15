from pwdlib import PasswordHash

MIN_PASSWORD_LENGTH = 12

_password_hasher = PasswordHash.recommended()

def hash_password(plain_password: str) -> str:
    """把明文密码转换为不可逆的 Argon2 密码哈希"""

    if len(plain_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must contain at least "
            f"{MIN_PASSWORD_LENGTH} characters."
        )

    return _password_hasher.hash(plain_password)

def verify_password(
        plain_password: str,
        stored_password_hash: str,
) -> bool:
    """验证明文密码是否与数据库中的哈希匹配"""

    return _password_hasher.verify(
        plain_password,
        stored_password_hash,
    )