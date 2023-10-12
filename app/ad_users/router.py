from fastapi import APIRouter, HTTPException, status, Response, Depends

from app.api_users.auth import get_password_hash, verify_password, authenticate_api_user, create_access_token
from app.api_users.dependencies import get_current_api_user
from app.api_users.models import ApiUsers
from app.api_users.shemas import SApiUserAuth
from app.api_users.dao import ApiUsersDAO
from app.exeptions import IncorrectEmailOrPassword

router = APIRouter(
    prefix='/functions',
    tags=['API Functions']
)


@router.post('/new_user')
async def add_new_ad_user(api_user: ApiUsers = Depends(get_current_api_user)):
    # print(user, type(user), user.email)
    # return await BookingDAO.find_all(user_id=user.id)
    return await ApiUsersDAO.find_all(id=1)
