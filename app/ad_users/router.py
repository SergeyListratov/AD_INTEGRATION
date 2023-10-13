from fastapi import APIRouter, HTTPException, status, Response, Depends

from app.ad_users.dao import AdUsersDAO
from app.api_users.dependencies import get_current_api_user
from app.ad_users.dependencies import create_ad_user
from app.api_users.models import ApiUsers
from app.api_users.shemas import SApiUserAuth
from app.api_users.dao import ApiUsersDAO
from app.exeptions import IncorrectEmailOrPassword

router = APIRouter(
    prefix='/functions',
    tags=['API Functions']
)


# @router.post('/add_new_user')
# async def add_new_ad_user(api_user: ApiUsers = Depends(get_current_api_user)):
#     # print(user, type(user), user.email)
#     # return await BookingDAO.find_all(user_id=user.id)
#     return await ApiUsersDAO.find_all(id=1)

@router.post('/add_new_user')
async def add_new_ad_user(api_user: ApiUsers = Depends(get_current_api_user)):
    # print(user, type(user), user.)
    # return await BookingDAO.find_all(user_id=user.id)
    return await AdUsersDAO.find_all(id=1)
