from fastapi import APIRouter, HTTPException, status, Response

from app.api_users.auth import get_password_hash, verify_password, authenticate_user, create_access_token
from app.api_users.shemas import SApiUserAuth
from app.api_users.dao import ApiUsersDAO


router = APIRouter(
    prefix='/auth',
    tags=['Auth & Users']
)


@router.post('/register')
async def register_user(user_date: SApiUserAuth):
    existing_user = await ApiUsersDAO.find_one_or_none(api_user_login_name=user_date.login)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    hashed_password = get_password_hash(user_date.password)
    await ApiUsersDAO.add(api_user_login_name=user_date.login, hashed_api_user_password=hashed_password)


@router.post('/login')
async def login_user(response: Response, user_date: SApiUserAuth):
    user = await authenticate_user(user_date.login, user_date.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    access_token = create_access_token({'sub': user.id})
    response.set_cookie('ad_access_token', access_token, httponly=True)
    return {'access_token': access_token}