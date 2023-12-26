from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def crypto_xor(message: str, secret: str='gH56!oi0' ) -> str:
    new_chars = list()
    i = 0

    for num_chr in (ord(c) for c in message):
        num_chr ^= ord(secret[i])
        new_chars.append(num_chr)

        i += 1
        if i >= len(secret):
            i = 0

    return ''.join(chr(c) for c in new_chars)


def encrypt_xor(message: str) -> str:
    return crypto_xor(message).encode('utf-8').hex()


def decrypt_xor(message_hex: str) -> str:
    message = bytes.fromhex(message_hex).decode('utf-8')
    return crypto_xor(message)


if __name__ == '__main__':
    # f = get_password_hash('bu')
    # g = verify_password('bu', '$2b$12$Xef2ybFiN7nSMQzMGkY9Eu9TGL9rsEGwjzLKF48OxejnLiOXw/2F6')
    # print(g)

    key = "gH56!oi0"

    encrypted = encrypt_xor('pg33014')
    print(encrypted)

    print(decrypt_xor(encrypted))

    print(decrypt_xor("172f0605115e5d"))
