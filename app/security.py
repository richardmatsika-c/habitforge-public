from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["argon2"],
    argon2__time_cost=3,  # Number of iterations
    argon2__memory_cost=65536,  # Memory usage (64MB)
    argon2__parallelism=1,  # Number of parallel threads
    argon2__hash_len=32,  # Hash length
    deprecated="auto",
)


# The rest remains the same...
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
