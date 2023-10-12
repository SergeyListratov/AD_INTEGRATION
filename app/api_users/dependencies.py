from fastapi import HTTPException, Request, Depends, status
from jose import jwt, JWTError, ExpiredSignatureError

from app.config import settings
from app.exeptions import TokenExpireException, TokenAbsentException, IncorrectTokenException, UserIsNotPresent
from app.api_users.dao import ApiUsersDAO
from app.api_users.models import ApiUsers


def get_token(request: Request):
    token = request.cookies.get('ad_access_token')
    if not token:
        raise TokenAbsentException
    return token


async def get_current_api_user(token: str = Depends(get_token)):
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, settings.ALG
        )
    except ExpiredSignatureError:
        raise TokenExpireException
    except JWTError:
        raise IncorrectTokenException
    user_id: str = payload.get("sub")
    if not user_id:
        raise UserIsNotPresent
    user = await ApiUsersDAO.find_one_or_none(id=int(user_id))
    if not user:
        raise UserIsNotPresent

    return user


async def get_current_admin_user(current_api_user: ApiUsers = Depends(get_current_api_user)):
    # if current_api_user.role != 'admin':
    #     raise PermissionDenied
    return current_api_user
