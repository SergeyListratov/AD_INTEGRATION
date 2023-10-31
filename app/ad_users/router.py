import asyncio
from fastapi import APIRouter, HTTPException, status, Response, Depends

from app.ad_users.shemas import SAdUser, SAdUserResponse
from app.api_users.dependencies import get_current_api_user
from app.ad_users.dependencies import create_ad_user
from app.api_users.models import ApiUsers
from app.api_users.shemas import SApiUserAuth
from app.api_users.dao import ApiUsersDAO
from app.ad_users.dao import AdUsersDAO
from app.exeptions import IncorrectEmailOrPassword, NotAuthorizedAction
from app.ad_users.dependencies import create_ad_user, transfer_ad_user, dismiss_ad_user

router = APIRouter(
    prefix='/ad_user',
    tags=['API add_transfer_dismiss']
)


@router.post('/integration')
async def ad_integration(ad_user: SAdUser, response_model: SAdUserResponse,
                         api_user: ApiUsers = Depends(get_current_api_user)):
    selector = {
        'transfer': transfer_ad_user,
        'dismiss': dismiss_ad_user,
        'create': create_ad_user
    }
    AdUsersDAO.data['first_name'] = ad_user.first_name
    AdUsersDAO.data['other_name'] = ad_user.other_name
    AdUsersDAO.data['last_name'] = ad_user.last_name
    AdUsersDAO.data['number'] = ad_user.number
    AdUsersDAO.data['division'] = ad_user.division
    AdUsersDAO.data['role'] = ad_user.role
    AdUsersDAO.data['action'] = ad_user.action
    AdUsersDAO.data['source'] = 'API'

    if api_user:
        response_model = selector[AdUsersDAO.data['action']](AdUsersDAO.data['first_name'], AdUsersDAO.data['other_name'],
                                                             AdUsersDAO.data['last_name'], AdUsersDAO.data['number'],
                                                             AdUsersDAO.data['division'], AdUsersDAO.data['role'])

        await AdUsersDAO.add()
        return response_model

    else:
        raise NotAuthorizedAction

# @router.post('/add')
# def add_user(new_ad_user: SAdUser, api_user: ApiUsers = Depends(get_current_api_user)):
#     username = 'g.bond'
#     forename = new_ad_user.first_name
#     surname = new_ad_user.last_name
#     division = 'TEST33'
#     new_password = 'Qwerty1'
#     if api_user:
#         return create_ad_user(username, forename, surname, division, new_password)
#     else:
#         raise NotAuthorizedAction
#
#
# @router.post('/transfer')
# def transfer_user(transferred_user: SAdUser, api_user: ApiUsers = Depends(get_current_api_user)):
#     username = 'g.bond'
#     forename = transferred_user.first_name
#     surname = transferred_user.last_name
#     division = 'TEST33'
#     tabel_number = transfer_user.tabel_number
#     if api_user:
#         return transfer_ad_user(username, forename, surname, division, tabel_number)
#     else:
#         raise NotAuthorizedAction
