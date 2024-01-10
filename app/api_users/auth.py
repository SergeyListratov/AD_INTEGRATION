from passlib.context import CryptContext
from jose import jwt
from datetime import timedelta, datetime

from pydantic import EmailStr

from app.api_users.dao import ApiUsersDAO
# from app.api_users.dao import UsersDAO

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(date: dict) -> str:
    to_encode = date.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, settings.ALG
    )
    return encoded_jwt


async def authenticate_api_user(login: str, password: str):
    user = await ApiUsersDAO.find_one_or_none(api_user_login_name=login)
    if not (user and verify_password(password, user.hashed_api_user_password)):
        return None
    return user





