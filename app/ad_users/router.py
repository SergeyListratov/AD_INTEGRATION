from fastapi import APIRouter, HTTPException, status, Response, Depends

from app.ad_users.dao import AdUsersDAO
from app.ad_users.shemas import SAdUser
from app.api_users.dependencies import get_current_api_user
from app.ad_users.dependencies import create_ad_user
from app.api_users.models import ApiUsers
from app.api_users.shemas import SApiUserAuth
from app.api_users.dao import ApiUsersDAO
from app.exeptions import IncorrectEmailOrPassword, NotAuthorizedAction
from app.ad_users.dependencies import create_ad_user, transfer_ad_user, dismiss_ad_user

router = APIRouter(
    prefix='/ad_user',
    tags=['API add_transfer_dismiss']
)


@router.post('/add')
def add_user(new_ad_user: SAdUser, api_user: ApiUsers = Depends(get_current_api_user)):
    username = 'g.bond'
    forename = new_ad_user.first_name
    surname = new_ad_user.last_name
    division = 'TEST33'
    new_password = 'Qwerty1'
    if api_user:
        return create_ad_user(username, forename, surname, division, new_password)
    else:
        raise NotAuthorizedAction


@router.post('/transfer')
def transfer_user(transferred_user: SAdUser, api_user: ApiUsers = Depends(get_current_api_user)):
    username = 'g.bond'
    forename = transferred_user.first_name
    surname = transferred_user.last_name
    division = 'TEST33'
    tabel_number = transfer_user.tabel_number
    if api_user:
        return transfer_ad_user(username, forename, surname, division, tabel_number)
    else:
        raise NotAuthorizedAction


@router.post('/dismiss')
def dismiss_user(dismissed_user: SAdUser, api_user: ApiUsers = Depends(get_current_api_user)):
    username = 'g.bond'
    forename = dismissed_user.first_name
    surname = dismissed_user.last_name
    division = 'TEST33'
    tabel_number = dismiss_user.tabel_number
    if api_user:
        return dismiss_ad_user(username, forename, surname, division, tabel_number)
    else:
        raise NotAuthorizedAction
