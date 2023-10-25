from fastapi import APIRouter, HTTPException, status, Response

from app.api_users.auth import get_password_hash, verify_password, authenticate_api_user, create_access_token
from app.api_users.shemas import SApiUserAuth
from app.api_users.dao import ApiUsersDAO
from app.exeptions import IncorrectEmailOrPassword, UserAlreadyExistsException

router = APIRouter(
    prefix='/auth',
    tags=['API auth']
)


# Роутер для регистрации в API
# @router.post('/register')
# async def register_api_user(user_date: SApiUserAuth):
#     existing_user = await ApiUsersDAO.find_one_or_none(api_user_login_name=user_date.login)
#     if existing_user:
#         raise UserAlreadyExistsException
#     hashed_password = get_password_hash(user_date.password)
#     await ApiUsersDAO.add(api_user_login_name=user_date.login, hashed_api_user_password=hashed_password)


@router.post('/login')
async def login_api_user(response: Response, user_date: SApiUserAuth):
    user = await authenticate_api_user(user_date.login, user_date.password)
    if not user:
        raise IncorrectEmailOrPassword
    access_token = create_access_token({'sub': str(user.id)})
    response.set_cookie('ad_access_token', access_token, httponly=True)
    return {'access_token': access_token}


@router.post('/logout')
async def logout_api_user(response: Response):
    response.delete_cookie('ad_access_token')
    return 'Api_user logout'
