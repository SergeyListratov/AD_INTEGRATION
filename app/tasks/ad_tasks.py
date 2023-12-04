import json
import string
import random

from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL
from ldap3.core.exceptions import LDAPInvalidDnError

from app.tasks.dao import InetDAO
from app.config import settings
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups
from ldap3.extend.microsoft.removeMembersFromGroups import ad_remove_members_from_groups


OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = 'DC=rpz,DC=local'
I_LDAP_BASE_DN = 'DC=rpz,DC=test'


def ldap_conn():
    server = Server(settings.AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.AD_USER, password=settings.AD_PASS, auto_bind=True)


def i_ldap_conn():
    server = Server(settings.I_AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.I_AD_USER, password=settings.I_AD_PASS, auto_bind=True)


''' Creatre Users in internet domian'''


def find_group_member_for_internet(group='To_internet') -> Optional[list[dict]]:
    cn = group
    i_usr_list = []
    user_list = search_gp_user(cn)['member']
    if user_list:
        for usr in user_list:
            usr_cn = usr.split(',')[0][3:]
            usr_div = usr.split(',')[2]
            i_usr_dn = f'CN={usr_cn},{usr_div},OU=USERInternal,DC=RPZ,DC=TEST'
            usr_dict = get_usr_attr(usr_cn)
            usr_dict['dn'] = i_usr_dn
            i_usr_list.append(usr_dict)

    return i_usr_list


def password_generator(length=8):
    characters = string.ascii_letters + string.digits
    password = ''.join(random.choice(characters) for _ in range(length))
    return password


def search_gp_user(gp_name, ldap_base_dn: str = LDAP_BASE_DN, ldap_conn=ldap_conn):
    gp_dict = dict()
    search_filter = f"(cn={gp_name})"
    with ldap_conn() as c:
        c.search(search_base=ldap_base_dn,
                 search_filter=search_filter,
                 search_scope=SUBTREE,
                 attributes=['member'],
                 get_operational_attributes=True)

        ad_atr_list: Optional[list[dict]] = json.loads(c.response_to_json())['entries']
    gp_dict['dn'] = ad_atr_list[0]['dn']
    gp_dict['member'] = ad_atr_list[0]['attributes']['member']

    return gp_dict


def get_usr_attr(usr_name, ldap_base_dn: str = LDAP_BASE_DN, ldap_conn=ldap_conn):
    user_attr_tuple = (
    'company', 'department', 'description', 'initials', 'sAMAccountName', 'telephoneNumber', 'title', 'sn', 'cn',
    'displayName', 'givenName')
    usr_dict = dict()
    search_filter = f"(cn={usr_name})"
    with ldap_conn() as c:
        c.search(search_base=ldap_base_dn,
                 search_filter=search_filter,
                 search_scope=SUBTREE,
                 attributes=ALL_ATTRIBUTES,
                 get_operational_attributes=True)

        ad_atr_list: Optional[list[dict]] = json.loads(c.response_to_json())['entries']

    usr_dict['dn'] = ad_atr_list[0]['dn']
    usr_dict['dn_local'] = ad_atr_list[0]['dn']
    usr_dict['attributes'] = dict()
    for attr in user_attr_tuple:
        if attr in ad_atr_list[0]['attributes']:
            usr_dict['attributes'][attr] = ad_atr_list[0]['attributes'][attr]

    return usr_dict


def trans_to_groups(dn_usr):
    dn_gp_in = 'CN=Internet,OU=Access,OU=Groups,DC=rpz,DC=local'
    dn_gp_out = 'CN=To_internet,OU=Access,OU=Groups,DC=rpz,DC=local'
    print(dn_usr)
    with ldap_conn() as conn:
        result_add = ad_add_members_to_groups(conn, dn_usr, dn_gp_in)
        result_del = ad_remove_members_from_groups(conn, dn_usr, dn_gp_out, fix=False)

    return result_add, result_del


async def create_i_ad_user() -> tuple[Any, Any, Any] | tuple[Any, Any, Any, Any] | dict[Any, Any]:
    result_dict = dict()
    i_usr_list = find_group_member_for_internet()
    if i_usr_list:
        with i_ldap_conn() as conn:
            for usr in i_usr_list:
                InetDAO.data['first_name'] = usr['attributes']['givenName']
                InetDAO.data['last_name'] = usr['attributes']['sn']
                InetDAO.data['division'] = usr['attributes']['department']
                InetDAO.data['role'] = usr['attributes']['title']
                InetDAO.data['number'] = usr['attributes']['initials']
                InetDAO.data['login_name'] = usr['attributes']['sAMAccountName']

                result = conn.add(dn=usr['dn'], object_class=OBJECT_CLASS, attributes=usr['attributes'])
                if not result:
                    if conn.result.get("description") == 'entryAlreadyExists':
                        result_local = trans_to_groups(usr['dn_local'])

                    msg = f'ERROR: User {usr["dn"].split(",")[0][3:]} was not created: {conn.result.get("description")}'
                    InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password'] = 'ERROR', msg, 'ERROR'
                    result_dict = InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password']
                    await InetDAO.add()

                    return result_dict

                # unlock and set password

                conn.extend.microsoft.unlock_account(user=usr['dn'])
                new_pass = password_generator()
                conn.extend.microsoft.modify_password(user=usr['dn'],
                                                      new_password=new_pass,
                                                      old_password=None)
                # Enable account - must happen after user password is set
                enable_account = {"userAccountControl": (MODIFY_REPLACE, [544])}
                conn.modify(usr['dn'], changes=enable_account)
                # Add groups
                gp = 'CN=intrfu,CN=Users,DC=RPZ,DC=TEST'
                result_inet = ad_add_members_to_groups(conn, usr['dn'], gp)
                result_local = trans_to_groups(usr['dn_local'])
                print(result_local)
                msg = f"OK. User {usr['dn'].split(',')[0][3:]} with pass {new_pass} was created in division {usr['dn'].split(',')[1][3:]} and added to group: {gp.split(',')[0][3:]}."
                InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password'] = 'OK', msg, new_pass
                result_dict = InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password'], InetDAO.data['login_name']

                await InetDAO.add()

                return result_dict

    else:
        return result_dict


if __name__ == '__main__':
    # print(i_ldap_conn())

    # print(password_generator())
    create_i_ad_user()

    # print(get_div_rol_descript(div, rol))
    # print(get_division(div))

    # file_prep('all.csv', 'r2.csv', '1.csv')

    '''
      f = 'roles.csv'
        ff = 'xmo1.txt'
        print(from_file_role_create(f, ff))
        # print(from_file_role_security(f, ff))
    '''

    jsn1 = {

        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Тест",
        "number": "33999",
        "division": "УТ (ТЕСТ1 БТ )",
        "role": "Специальная тестовая должность 1",
        "action": "create"

    }

    jsn2 = {
        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Тест",
        "number": "33999",
        "division": "МТ (ТЕСТ1 БО)",
        "role": "Специальная тестовая должность 2",
        "action": "transfer"
    }

    jsn3 = {
        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Тест",
        "number": "33999",
        "division": "МТ (ТЕСТ1 БО)",
        "role": "Специальная тестовая должность 2",
        "action": "dismiss"
    }

# ad = director(jsn3)
# print(ad)
