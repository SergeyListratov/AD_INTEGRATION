import json
import string
import random
import time

import schedule

from pykeepass import PyKeePass

import asyncio
from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL
from smb.SMBConnection import SMBConnection
import tempfile

from app.tasks.dao import InetDAO
from app.config import settings
from typing import Optional, Any

from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups
from ldap3.extend.microsoft.removeMembersFromGroups import ad_remove_members_from_groups

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = settings.AD_BASE
I_LDAP_BASE_DN = settings.I_AD_BASE


def ldap_conn():
    server = Server(settings.AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.AD_USER, password=settings.AD_PASS, auto_bind=True)


def i_ldap_conn():
    server = Server(settings.I_AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.I_AD_USER, password=settings.I_AD_PASS, auto_bind=True)


''' Create Users in internet domain'''


def find_group_member_for_internet(group='To_internet') -> Optional[list[dict]]:
    cn = group
    i_usr_list = []
    user_list = search_gp_user(cn)['member']
    if user_list:
        for usr in user_list:
            usr_cn = usr.split(',')[0][3:]
            usr_div = usr.split(',')[2]
            i_usr_dn = f'CN={usr_cn},{usr_div},{settings.I_AD_OU},{I_LDAP_BASE_DN}'
            usr_dict = get_usr_attr(usr_cn)
            usr_dict['dn'] = i_usr_dn
            i_usr_list.append(usr_dict)

    return i_usr_list


def password_generator(length=8):
    characters = string.ascii_letters + string.digits
    psw_d = ''.join(random.choice(string.digits) for _ in range(1))
    psw_l = ''.join(random.choice(string.ascii_letters) for _ in range(1))
    psw_all = ''.join(random.choice(characters) for _ in range(length - 2))
    characters = psw_d + psw_l + psw_all
    lst = list(characters)
    random.shuffle(lst)
    password = ''.join(lst).rstrip().lstrip()
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
        'displayName', 'givenName', 'userPrincipalName')
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
    dn_gp_in = settings.AD_GP_IN
    dn_gp_out = settings.AD_GP_OUT
    with ldap_conn() as conn:
        result_add = ad_add_members_to_groups(conn, dn_usr, dn_gp_in)
        result_del = ad_remove_members_from_groups(conn, dn_usr, dn_gp_out, fix=False)

    return result_add, result_del


def create_i_ad_user() -> tuple[Any, Any, Any] | tuple[Any, Any, Any, Any] | dict[Any, Any]:
    result_dict = dict()
    i_usr_list = find_group_member_for_internet()
    if i_usr_list:
        with i_ldap_conn() as conn:
            for usr in i_usr_list:
                empty_fild_list = []
                if 'givenName' in usr['attributes']:
                    InetDAO.data['first_name'] = usr['attributes']['givenName']
                else:
                    InetDAO.data['first_name'] = ''
                    empty_fild_list.append('Имя')
                if 'sn' in usr['attributes']:
                    InetDAO.data['last_name'] = usr['attributes']['sn']
                else:
                    InetDAO.data['last_name'] = ''
                    empty_fild_list.append('Фамилия')
                if 'department' in usr['attributes']:
                    InetDAO.data['division'] = usr['attributes']['department']
                else:
                    InetDAO.data['division'] = ''
                    empty_fild_list.append('Подразделение')
                if 'title' in usr['attributes']:
                    InetDAO.data['role'] = usr['attributes']['title']
                else:
                    InetDAO.data['role'] = ''
                    empty_fild_list.append('Должность')
                if 'initials' in usr['attributes']:
                    InetDAO.data['number'] = usr['attributes']['initials']
                else:
                    InetDAO.data['number'] = ''
                    empty_fild_list.append('Табельный')
                if 'sAMAccountName' in usr['attributes']:
                    InetDAO.data['login_name'] = usr['attributes']['sAMAccountName']
                else:
                    InetDAO.data['login_name'] = ''
                    empty_fild_list.append('Логин')
                if 'userPrincipalName' in usr['attributes']:
                    upn_list = usr['attributes']['userPrincipalName'].split('@')
                    usr['attributes']['userPrincipalName'] = f'{upn_list[0]}@{settings.I_AD_DOMEN}'
                else:
                    usr['attributes'][
                        'userPrincipalName'] = f"{usr['attributes']['sAMAccountName']}@{settings.I_AD_DOMEN}"

                empty_fild = ', '.join(empty_fild_list)

                if empty_fild:
                    msg = f'ERROR: User {usr["dn"].split(",")[0][3:]} was not created, user have empty fild: {empty_fild}.'
                    InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password'] = 'ERROR', msg, 'ERROR'
                    result_dict = InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password']

                    # loop = asyncio.get_event_loop()
                    # loop.run_until_complete(InetDAO.add())
                    InetDAO.no_async_add()
                    InetDAO.postal()

                    return result_dict

                result = conn.add(dn=usr['dn'], object_class=OBJECT_CLASS, attributes=usr['attributes'])
                if not result:
                    if conn.result.get("description") == 'entryAlreadyExists':
                        result_local = trans_to_groups(usr['dn_local'])

                    msg = f'ERROR: User {usr["dn"].split(",")[0][3:]} was not created: {conn.result.get("description")}'
                    InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password'] = 'ERROR', msg, 'ERROR'
                    result_dict = InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password']

                    # loop = asyncio.get_event_loop()
                    # loop.run_until_complete(InetDAO.add())
                    InetDAO.no_async_add()

                    InetDAO.postal()

                    return result_dict

                # unlock and set password

                new_pass = password_generator()

                conn.extend.microsoft.unlock_account(user=usr['dn'])


                conn.extend.microsoft.modify_password(user=usr['dn'],
                                                            new_password=new_pass + new_pass,
                                                            old_password=None)
                # Enable account - must happen after user password is set
                enable_account = {"userAccountControl": (MODIFY_REPLACE, [512])}
                conn.modify(usr['dn'], changes=enable_account)
                # Add groups
                gp = settings.I_AD_GROUP
                result_inet = ad_add_members_to_groups(conn, usr['dn'], gp)
                result_local = trans_to_groups(usr['dn_local'])


                msg = f"OK. User {usr['dn'].split(',')[0][3:]} with pass '{new_pass}' was created in division {usr['dn'].split(',')[1][3:]} and added to group: {gp.split(',')[0][3:]}."
                InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password'] = 'OK', msg, new_pass
                result_dict = InetDAO.data['status'], InetDAO.data['message'], InetDAO.data['i_password'], InetDAO.data[
                    'login_name']

                # loop = asyncio.get_event_loop()
                # loop.run_until_complete(InetDAO.add())
                InetDAO.no_async_add()

                InetDAO.postal()
                mailto = f'{InetDAO.data["login_name"]}@{settings.I_AD_DOMEN}'
                InetDAO.postal(to=mailto)

                InetDAO.keepass()

                return result_dict

    else:
        return result_dict


def get_smb_conn():
    smb_conn = SMBConnection(settings.SMB_USER, settings.SMB_PASS, settings.SMB_SRV,
                             domain=settings.SMB_DOMAIN, use_ntlm_v2=True,
                             remote_name=settings.SMB_SRV)
    smb_conn.connect(settings.SMB_IP, settings.SMB_PORT)

    return smb_conn


def kee(smb_conn, title, username, password, description):
    descrip = f'NEW+ \n {description}'
    temp_path = settings.KEEPASS_TEMP_PATH
    group_name = settings.KEEPASS_GROUP_NAME
    prefix, suffix = settings.KEEPASS_DB.split('.')
    with tempfile.NamedTemporaryFile(prefix=f'{prefix}', suffix=f'.{suffix}', dir=temp_path) as file_obj:
        file_attr, old_size = smb_conn.retrieveFile(settings.SMB_SERVICE, settings.KEEPASS_URL, file_obj)
        kee_path = file_obj.name

        with PyKeePass(kee_path, password=settings.KEEPASS_MASTER_KEY) as kp:
            while kp.find_entries(title=title, first=True):
                title = f'{title}_$'
            group = kp.find_groups(name=group_name, first=True)
            kp.add_entry(group, title=title, username=username, password=password, notes=descrip)
            kp.save()
            entry = kp.find_entries(title=title, first=True)
        with open(kee_path, 'rb+') as kee_obj:
            new_size = smb_conn.storeFile(settings.SMB_SERVICE, settings.KEEPASS_URL, kee_obj)
    kee_dict = {'old_size': old_size, 'new_size': new_size, 'user': entry}

    return kee_dict


def scheduler_inet_user():
    print('Start Inet User Create')
    schedule.every(settings.SCHEDULE_TIME).minutes.do(create_i_ad_user)
    while True:
        schedule.run_pending()
        time.sleep(1)

