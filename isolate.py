from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)

if __name__ == '__main__':
    f = get_password_hash('bu')
    g = verify_password('bu', '$2b$12$Xef2ybFiN7nSMQzMGkY9Eu9TGL9rsEGwjzLKF48OxejnLiOXw/2F6')
    print(g)