from fastapi import APIRouter, HTTPException, status, Response, Depends

from app.ad_users.dao import AdUsersDAO
from app.ad_users.shemas import SAdUser, SAdUserResponse
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


@router.post('/integration')
def ad_integration(ad_user: SAdUser, response_model: SAdUserResponse,
                   api_user: ApiUsers = Depends(get_current_api_user)):
    selector = {
        'transfer': transfer_ad_user,
        'dismiss': dismiss_ad_user,
        'create': create_ad_user
    }

    # AdUsersDAO.first_name = first_name
    # AdUsersDAO.other_name = other_name
    # AdUsersDAO.last_name = last_name
    # AdUsersDAO.number = number
    # AdUsersDAO.division = division
    # AdUsersDAO.role = role
    # AdUsersDAO.action = action

    AdUsersDAO.first_name = ad_user.first_name
    AdUsersDAO.other_name = ad_user.other_name
    AdUsersDAO.last_name = ad_user.last_name
    AdUsersDAO.number = ad_user.number
    AdUsersDAO.division = ad_user.division
    AdUsersDAO.role = ad_user.role
    AdUsersDAO.action = ad_user.action
    if api_user:
        return selector[AdUsersDAO.action](AdUsersDAO.first_name, AdUsersDAO.other_name, AdUsersDAO.last_name,
                                           AdUsersDAO.number, AdUsersDAO.division, AdUsersDAO.role)
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
